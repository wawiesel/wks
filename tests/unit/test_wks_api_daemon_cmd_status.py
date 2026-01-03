"""Integration-ish tests for wks.api.daemon.cmd_status without mocks."""

import time

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop


@pytest.mark.daemon
def test_cmd_status_reads_written_status(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Start to create daemon.json
    start_result = run_cmd(cmd_start)
    assert start_result.success is True

    # Status should read daemon.json
    status_result = run_cmd(cmd_status)
    assert status_result.success is True
    assert status_result.output["running"] is True
    assert status_result.output["restrict_dir"] == ""
    assert status_result.output["log_path"].endswith(WKSConfig.get_logfile_path().name)

    # Stop to clean up
    stop_result = run_cmd(cmd_stop)
    assert stop_result.success is True


@pytest.mark.daemon
def test_cmd_status_reflects_log_warnings(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    run_cmd(cmd_start)

    log_path = WKSConfig.get_logfile_path()
    # Append messages; the daemon subprocess extracts WARN/ERROR lines into daemon.json.
    with log_path.open("a", encoding="utf-8") as f:
        f.write("WARN: something happened\n")
        f.write("ERROR: badness\n")

    # Poll until daemon.json reflects the extracted messages (it is rewritten each loop).
    deadline = time.time() + 5.0
    while True:
        status_result = run_cmd(cmd_status)
        assert status_result.success is True
        warnings = status_result.output.get("warnings", [])
        errors = status_result.output.get("errors", [])
        if "WARN: something happened" in warnings and "ERROR: badness" in errors:
            break
        if time.time() > deadline:
            raise AssertionError(
                f"daemon.json did not reflect log messages in time. warnings={warnings!r} errors={errors!r}"
            )
        time.sleep(0.1)

    run_cmd(cmd_stop)


@pytest.mark.daemon
def test_status_updates_timestamp_when_running(monkeypatch, tmp_path):
    """Test that last_sync timestamp updates on status checks if running."""
    cfg = minimal_wks_config()
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.monitor.filter.include_paths.append(str(tmp_path))
    cfg.save()

    run_cmd(cmd_start)

    # First status check
    res1 = run_cmd(cmd_status)
    t1 = res1.output["last_sync"]
    assert t1 is not None

    time.sleep(1.1)

    # Second status check
    res2 = run_cmd(cmd_status)
    t2 = res2.output["last_sync"]
    assert t2 is not None

    assert t1 != t2, f"Timestamp should update on each status check when running (t1={t1}, t2={t2})"

    run_cmd(cmd_stop)


@pytest.mark.daemon
def test_status_preserves_timestamp_when_stopped(monkeypatch, tmp_path):
    """Test that last_sync timestamp is preserved (not updated) if stopped."""
    cfg = minimal_wks_config()
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    run_cmd(cmd_start)
    time.sleep(0.5)
    run_cmd(cmd_stop)

    # Wait for child process to fully exit and settle status file writes
    time.sleep(2.0)

    # First status check on stopped daemon
    res1 = run_cmd(cmd_status)
    assert res1.output["running"] is False
    # Since we don't read stale status, last_sync is None when stopped
    assert res1.output["last_sync"] is None

    time.sleep(1.1)

    # Second status check
    res2 = run_cmd(cmd_status)
    assert res2.output["last_sync"] is None


def test_cmd_status_stale_lock(monkeypatch, tmp_path):
    """Test cmd_status when lock exists but PID is dead."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create config
    cfg = minimal_wks_config()
    cfg.save()

    # Create stale lock
    lock_path = wks_home / "daemon.lock"
    # Use a large PID that is unlikely to exist
    lock_path.write_text("999999\n")

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["running"] is False


def test_cmd_status_running_corrupt_json(monkeypatch, tmp_path):
    """Test cmd_status when running but daemon.json is corrupt."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.save()

    # Create running lock
    import os

    lock_path = wks_home / "daemon.lock"
    lock_path.write_text(f"{os.getpid()}\n")

    # Create corrupt json
    status_path = wks_home / "daemon.json"
    status_path.write_text("corrupt {")

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["running"] is True
    assert result.output["restrict_dir"] == "UNKNOWN"
