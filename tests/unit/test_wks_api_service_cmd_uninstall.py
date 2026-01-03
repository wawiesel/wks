"""Unit tests for wks.api.service.cmd_uninstall module.

We prefer not to use mocks in almost every case, but there is not a good way
to test uninstalling a service except with mocks.

"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import cmd_uninstall
from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_cmd_uninstall_success(tracked_wks_config, monkeypatch):
    """Test cmd_uninstall with successful uninstallation."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )  # type: ignore
    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.uninstall_service.return_value = {
        "success": True,
        "label": "com.test.wks",
    }

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_uninstall_validation_failure(tracked_wks_config, monkeypatch):
    """Test cmd_uninstall validation failure."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(cmd_uninstall.Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_uninstall_failure(tracked_wks_config, monkeypatch):
    """Test cmd_uninstall failure from backend."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service = mock_service_cls.return_value.__enter__.return_value
    mock_service.uninstall_service.return_value = {"success": False, "error": "Uninstall failed"}
    monkeypatch.setattr(cmd_uninstall, "Service", mock_service_cls)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert result.result == "Uninstall failed"


def test_cmd_uninstall_exception(tracked_wks_config, monkeypatch):
    """Test cmd_uninstall exception."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.side_effect = Exception("Boom")
    monkeypatch.setattr(cmd_uninstall, "Service", mock_service_cls)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert "Error uninstalling service: Boom" in result.result


def test_cmd_uninstall_not_implemented(tracked_wks_config, monkeypatch):
    """Test cmd_uninstall NotImplementedError."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.side_effect = NotImplementedError("Not supported")
    monkeypatch.setattr(cmd_uninstall, "Service", mock_service_cls)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert "Error: Service uninstallation not supported" in result.result
