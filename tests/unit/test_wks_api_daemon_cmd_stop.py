"""Integration-ish tests for wks.api.daemon.cmd_stop without mocks."""

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_stop import cmd_stop
from wks.api.daemon._read_status_file import read_status_file


@pytest.mark.daemon
def test_cmd_stop_clears_lock_and_updates_status(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    run_cmd(cmd_start)
    assert (wks_home / "daemon.lock").exists()
    assert (wks_home / "daemon.json").exists()

    result = run_cmd(cmd_stop)
    assert result.success is True
    assert result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()

    status = read_status_file(wks_home)
    assert status["running"] is False


@pytest.mark.daemon
def test_cmd_stop_idempotent(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    run_cmd(cmd_start)
    first = run_cmd(cmd_stop)
    assert first.success is True
    second = run_cmd(cmd_stop)
    assert second.success is True
    assert second.output["stopped"] is True
