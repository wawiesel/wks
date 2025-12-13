"""Integration-ish tests for wks.api.daemon.cmd_status without mocks."""

import time

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.daemon import cmd_start, cmd_status, cmd_stop


@pytest.mark.daemon
def test_cmd_status_reads_written_status(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Start to create daemon.json
    start_result = run_cmd(cmd_start.cmd_start)
    assert start_result.success is True

    # Status should read daemon.json
    status_result = run_cmd(cmd_status.cmd_status)
    assert status_result.success is True
    assert status_result.output["running"] is True
    assert status_result.output["restrict_dir"] == ""
    assert status_result.output["log_path"].endswith("daemon.log")

    # Stop to clean up
    stop_result = run_cmd(cmd_stop.cmd_stop)
    assert stop_result.success is True


@pytest.mark.daemon
def test_cmd_status_reflects_log_warnings(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    run_cmd(cmd_start.cmd_start)

    log_path = wks_home / "logs" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Append messages; the daemon subprocess extracts WARN/ERROR lines into daemon.json.
    with log_path.open("a", encoding="utf-8") as f:
        f.write("WARN: something happened\n")
        f.write("ERROR: badness\n")

    # Poll until daemon.json reflects the extracted messages (it is rewritten each loop).
    deadline = time.time() + 5.0
    while True:
        status_result = run_cmd(cmd_status.cmd_status)
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

    run_cmd(cmd_stop.cmd_stop)
