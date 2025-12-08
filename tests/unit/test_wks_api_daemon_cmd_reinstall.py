"""Unit tests for wks.api.daemon.cmd_reinstall module."""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.daemon import cmd_reinstall
from wks.api.daemon.DaemonConfig import DaemonConfig

pytestmark = pytest.mark.daemon


def test_cmd_reinstall_success(patch_wks_config, monkeypatch):
    """Test cmd_reinstall with successful reinstallation."""
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

    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {"installed": True}
    mock_impl.uninstall_service.return_value = {"success": True, "label": "com.test.wks"}
    mock_impl.install_service.return_value = {"success": True, "label": "com.test.wks"}

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "macos._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    # Mock cmd_uninstall and cmd_install
    from wks.api.StageResult import StageResult

    def mock_uninstall():
        result = StageResult(announce="Uninstalling...", progress_callback=lambda r: iter([(1.0, "Complete")]))
        result.result = "Uninstalled"
        result.output = {"errors": [], "warnings": []}
        result.success = True
        return result

    def mock_install():
        result = StageResult(announce="Installing...", progress_callback=lambda r: iter([(1.0, "Complete")]))
        result.result = "Installed"
        result.output = {"errors": [], "warnings": []}
        result.success = True
        return result

    monkeypatch.setattr(cmd_reinstall, "cmd_uninstall", mock_uninstall)
    monkeypatch.setattr(cmd_reinstall, "cmd_install", mock_install)

    result = run_cmd(cmd_reinstall.cmd_reinstall)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output

