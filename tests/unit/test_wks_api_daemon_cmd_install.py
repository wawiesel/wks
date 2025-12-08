"""Unit tests for wks.api.daemon.cmd_install module."""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.daemon import cmd_install
from wks.api.daemon.DaemonConfig import DaemonConfig

pytestmark = pytest.mark.daemon


def test_cmd_install_success(patch_wks_config, monkeypatch):
    """Test cmd_install with successful installation."""
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
    mock_impl.install_service.return_value = {
        "success": True,
        "label": "com.test.wks",
        "plist_path": "/path/to/plist",
    }

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "macos._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output

