"""Unit tests for wks.api.service.cmd_status module.

Note: we do not use mocks for this test.
"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import cmd_status
from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_cmd_status_success(tracked_wks_config, monkeypatch, tmp_path):
    """Test cmd_status with successful status check."""
    tracked_wks_config.service = ServiceConfig.model_validate(
        {
            "type": "darwin",
            "data": {
                "label": "com.test.wks",
                "keep_alive": True,
                "run_at_load": False,
            },
        }
    )

    # Mock WKS_HOME to isolated tmp_path preventing real daemon.json read
    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    # Mock daemon implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {
        "installed": True,
        "running": True,
        "pid": 12345,
        "label": "com.test.wks",
    }

    # Mock the import and class instantiation
    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)
    # Mock _pid_running to return True
    monkeypatch.setattr(cmd_status, "_pid_running", lambda pid: True)

    result = run_cmd(cmd_status.cmd_status)
    assert result.success is True
    assert result.output["running"] is True
    assert result.output["installed"] is True
    assert result.output["pid"] == 12345
    assert result.output["log_path"].endswith("daemon.json")
    assert "errors" in result.output and result.output["errors"] == []
    assert "warnings" in result.output and result.output["warnings"] == []


def test_cmd_status_not_installed(tracked_wks_config, monkeypatch, tmp_path):
    """Test cmd_status when service is not installed."""
    tracked_wks_config.service = ServiceConfig.model_validate(
        {
            "type": "darwin",
            "data": {
                "label": "com.test.wks",
                "keep_alive": True,
                "run_at_load": False,
            },
        }
    )

    # Mock WKS_HOME to isolated tmp_path
    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    # Mock daemon implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {
        "installed": False,
        "running": False,
    }

    # Mock the import and class instantiation
    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_status.cmd_status)
    assert result.success is True
    assert result.output["running"] is False
    assert result.output["installed"] is False
    assert result.output["log_path"].endswith("daemon.json")
    assert "errors" in result.output and result.output["errors"] == []
    assert "warnings" in result.output and result.output["warnings"] == []
