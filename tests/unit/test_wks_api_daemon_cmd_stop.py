"""Integration-ish tests for wks.api.daemon.cmd_stop without mocks."""

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_stop import cmd_stop


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

    import json

    status = json.loads((wks_home / "daemon.json").read_text())
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


@pytest.mark.daemon
def test_cmd_stop_failure(monkeypatch, tmp_path):
    """Test cmd_stop behavior on Exception."""
    from unittest.mock import patch

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    with patch("wks.api.daemon.cmd_stop.Daemon") as mock_daemon_class:
        mock_daemon_instance = mock_daemon_class.return_value
        mock_daemon_instance.stop.side_effect = Exception("Stop failed")

        res = run_cmd(cmd_stop)
        assert res.success is False
        assert "Stop failed" in res.result
        assert res.output["stopped"] is False
