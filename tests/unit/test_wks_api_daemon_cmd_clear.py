"""Unit tests for wks.api.daemon.cmd_clear."""

import json

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.daemon.cmd_clear import cmd_clear
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_status import cmd_status
from wks.api.daemon.cmd_stop import cmd_stop


@pytest.mark.daemon
def test_daemon_clear_when_stopped(monkeypatch, tmp_path):
    """Test that clear resets logs and status when daemon is stopped."""
    cfg = minimal_wks_config()
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Create dummy daemon.json with messy state
    status_path = wks_home / "daemon.json"
    status_path.write_text('{"running": false, "errors": ["old error"]}')

    # Create logs with messy content
    log_path = WKSConfig.get_logfile_path()
    log_path.write_text("Old log content\n")

    # Run clear
    clear_result = run_cmd(cmd_clear)
    assert clear_result.success is True
    assert "Daemon state cleared" in clear_result.result

    # Verify status is reset
    new_status = json.loads(status_path.read_text())
    assert new_status["running"] is False
    assert new_status["errors"] == []
    assert new_status["pid"] is None
    assert new_status["last_sync"] is None

    # Verify logs are cleared (empty file)
    assert log_path.exists()
    assert log_path.read_text() == ""


@pytest.mark.daemon
def test_daemon_clear_blocked_when_running(monkeypatch, tmp_path):
    """Test that clear refuses to run if daemon is running (lock file exists and alive)."""
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 2.0  # Slow sync to ensure it stays alive
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Start daemon
    run_cmd(cmd_start)

    # Verify it started
    status_res = run_cmd(cmd_status)
    assert status_res.output["running"] is True

    # Attempt clear
    clear_result = run_cmd(cmd_clear)
    assert clear_result.success is False
    assert "Cannot clear while daemon is running" in clear_result.result

    # Verify status still accessible/running
    status_path = wks_home / "daemon.json"
    status_after = json.loads(status_path.read_text())
    assert status_after["running"] is True

    # Cleanup
    run_cmd(cmd_stop)


def test_daemon_clear_errors_only(monkeypatch, tmp_path):
    """Test that --errors-only removes only ERROR entries from the logfile."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.save()

    log_path = WKSConfig.get_logfile_path()
    log_path.write_text(
        "[2026-01-01T00:00:00+00:00] [daemon] INFO: started\n"
        "[2026-01-01T00:00:01+00:00] [link.sync] ERROR: sync failure\n"
        "[2026-01-01T00:00:02+00:00] [daemon] WARN: slow sync\n"
        "[2026-01-01T00:00:03+00:00] [link.sync] ERROR: another failure\n",
        encoding="utf-8",
    )

    result = run_cmd(cmd_clear, errors_only=True)
    assert result.success is True
    assert "2" in result.result  # "Cleared 2 error entries"

    content = log_path.read_text(encoding="utf-8")
    assert "INFO: started" in content
    assert "WARN: slow sync" in content
    assert "ERROR" not in content


def test_daemon_clear_stale_lock(monkeypatch, tmp_path):
    """Test that clear proceeds if lock is stale."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.save()

    lock_path = wks_home / "daemon.lock"
    # Use a large PID that is unlikely to exist
    lock_path.write_text("999999\n")

    result = run_cmd(cmd_clear)
    assert result.success is True
    assert not lock_path.exists()
