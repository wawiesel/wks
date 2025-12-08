"""Unit tests for wks.api.daemon.cmd_restart module."""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.daemon import cmd_restart
from wks.api.daemon.DaemonConfig import DaemonConfig

pytestmark = pytest.mark.daemon


def test_cmd_restart_success(patch_wks_config, monkeypatch):
    """Test cmd_restart with successful restart."""
    patch_wks_config.daemon = DaemonConfig(
        type="macos",
        data={
            "label": "com.test.wks",
            "log_file": "daemon.log",
            "error_log_file": "daemon.error.log",
            "keep_alive": True,
            "run_at_load": False,
        },
    )

    # Mock cmd_stop and cmd_start to succeed
    from wks.api.StageResult import StageResult

    def mock_stop():
        result = StageResult(announce="Stopping...", progress_callback=lambda r: iter([(1.0, "Complete")]))
        result.result = "Stopped"
        result.output = {"errors": [], "warnings": []}
        result.success = True
        return result

    def mock_start():
        result = StageResult(announce="Starting...", progress_callback=lambda r: iter([(1.0, "Complete")]))
        result.result = "Started"
        result.output = {"errors": [], "warnings": []}
        result.success = True
        return result

    monkeypatch.setattr(cmd_restart, "cmd_stop", mock_stop)
    monkeypatch.setattr(cmd_restart, "cmd_start", mock_start)

    result = run_cmd(cmd_restart.cmd_restart)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output

