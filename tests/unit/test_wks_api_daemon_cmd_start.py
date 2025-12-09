"""Unit tests for wks.api.daemon.cmd_start module."""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.daemon import cmd_start
from wks.api.daemon.DaemonConfig import DaemonConfig

pytestmark = pytest.mark.daemon


def test_cmd_start_success(patch_wks_config, monkeypatch):
    """Test cmd_start with successful start."""
    patch_wks_config.daemon = DaemonConfig(
        type="macos",
        data={
            "label": "com.test.wks",
            "log_file": "daemon.log",
            "keep_alive": True,
            "run_at_load": False,
        },
    )

    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {"installed": True, "running": False}
    mock_impl.start_service.return_value = {"success": True, "label": "com.test.wks"}

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "macos._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)
    monkeypatch.setattr(cmd_start, "_validate_backend_type", lambda bt: (True, None))
    monkeypatch.setattr(cmd_start, "_get_daemon_impl", lambda bt, cfg: mock_impl)
    monkeypatch.setattr(cmd_start, "_start_via_service", lambda impl, bt: {
        "success": True,
        "output": {"label": "com.test.wks", "method": "service", "errors": [], "warnings": []},
        "result_msg": "Daemon started successfully",
    })

    result = run_cmd(cmd_start.cmd_start)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output
