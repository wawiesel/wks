"""Integration-ish tests for wks.api.daemon.cmd_status without mocks."""

import time
from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd, minimal_wks_config
from wks.api.daemon import cmd_start, cmd_stop, cmd_status


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
    log_path.write_text("WARN: something happened\nERROR: badness\n", encoding="utf-8")

    time.sleep(0.1)
    status_result = run_cmd(cmd_status.cmd_status)
    assert status_result.success is True
    assert "WARN: something happened" in status_result.output["warnings"]
    assert "ERROR: badness" in status_result.output["errors"]

    run_cmd(cmd_stop.cmd_stop)
