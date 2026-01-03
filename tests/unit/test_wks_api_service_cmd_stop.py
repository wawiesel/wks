"""Unit tests for wks.api.service.cmd_stop module.

We prefer not to use mocks in almost every case, but there is not a good way
to test stopping a service except with mocks.

"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import cmd_stop
from wks.api.service.ServiceConfig import ServiceConfig

pytestmark = pytest.mark.daemon


def test_cmd_stop_not_installed(tracked_wks_config, monkeypatch):
    """Test cmd_stop when service is not installed."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )  # type: ignore
    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = {"installed": False}

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "not installed" in result.result.lower()
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_stop_success(tracked_wks_config, monkeypatch):
    """Test cmd_stop successful stop."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    # Mock backend
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = {"installed": True}
    mock_service.stop_service.return_value = {"success": True}

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.return_value = mock_service
    monkeypatch.setattr(cmd_stop, "Service", mock_service_cls)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is True
    assert "Service stopped successfully" in result.result


def test_cmd_stop_already_stopped(tracked_wks_config, monkeypatch):
    """Test cmd_stop when service is already stopped."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service = MagicMock()
    mock_service.get_service_status.return_value = {"installed": True}
    mock_service.stop_service.return_value = {"success": True, "note": "already stopped"}

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.return_value = mock_service
    monkeypatch.setattr(cmd_stop, "Service", mock_service_cls)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is True
    assert "Service is already stopped" in result.result


def test_cmd_stop_failure(tracked_wks_config, monkeypatch):
    """Test cmd_stop failure."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service = MagicMock()
    mock_service.get_service_status.return_value = {"installed": True}
    mock_service.stop_service.return_value = {"success": False, "error": "Stop failed"}

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.return_value = mock_service
    monkeypatch.setattr(cmd_stop, "Service", mock_service_cls)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error stopping service: Stop failed" in result.result


def test_cmd_stop_validation_failure(tracked_wks_config, monkeypatch):
    """Test cmd_stop validation failure."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(cmd_stop.Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_stop_exception(tracked_wks_config, monkeypatch):
    """Test cmd_stop exception."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.side_effect = Exception("Boom")
    monkeypatch.setattr(cmd_stop, "Service", mock_service_cls)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error stopping service: Boom" in result.result


def test_cmd_stop_not_implemented(tracked_wks_config, monkeypatch):
    """Test cmd_stop NotImplementedError."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.side_effect = NotImplementedError("Not supported")
    monkeypatch.setattr(cmd_stop, "Service", mock_service_cls)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error: Service stop not supported" in result.result
