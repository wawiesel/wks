"""Integration-ish tests for wks.api.daemon.cmd_start without mocks."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd, minimal_wks_config
from wks.api.daemon import cmd_start, cmd_stop


@pytest.mark.daemon
def test_cmd_start_creates_artifacts(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    restrict = tmp_path / "watch"
    restrict.mkdir(parents=True, exist_ok=True)

    start_result = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert start_result.success is True
    assert start_result.output["running"] is True

    # Artifacts should exist
    assert (wks_home / "daemon.json").exists()
    assert (wks_home / "logs" / "daemon.log").exists()
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop.cmd_stop)
    assert stop_result.success is True
    assert stop_result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()


@pytest.mark.daemon
def test_cmd_start_twice_emits_warning(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    restrict = tmp_path / "watch"
    restrict.mkdir(parents=True, exist_ok=True)

    first = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert first.success is True
    assert first.output["running"] is True

    # Second start should succeed but log a warning
    second = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert second.success is True
    assert second.output["running"] is True

    log_path = wks_home / "logs" / "daemon.log"
    log_text = log_path.read_text()
    assert "WARN: Daemon already running" in log_text
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop.cmd_stop)
    assert stop_result.success is True
    assert stop_result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()
