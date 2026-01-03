"""Unit tests for wks.api.service.cmd_start module.

We prefer not to use mocks in almost every case, but there is not a good way
to test starting a service except with mocks.

"""

from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import run_cmd
from wks.api.service import ServiceStartOutput, cmd_start
from wks.api.service.Service import Service
from wks.api.service.ServiceConfig import ServiceConfig
from wks.api.service.ServiceStatus import ServiceStatus

pytestmark = pytest.mark.daemon


def test_cmd_start_success(tracked_wks_config, monkeypatch):
    """Test cmd_start with successful start."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.wks", "keep_alive": True, "run_at_load": False},  # type: ignore
    )  # type: ignore
    # Mock backend implementation
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=True, unit_path="/tmp/test.plist", running=False
    )
    mock_impl.start_service.return_value = {"success": True, "label": "com.test.wks"}

    mock_impl_class = MagicMock(return_value=mock_impl)
    mock_module = MagicMock()
    mock_module._Impl = mock_impl_class

    original_import = __import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if "darwin._Impl" in name:
            return mock_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", mock_import)
    monkeypatch.setattr(
        Service,
        "start_via_service",
        lambda self: ServiceStartOutput(
            errors=[],
            warnings=[],
            message="Service started successfully",
            running=True,
        ),
    )

    result = run_cmd(cmd_start.cmd_start)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_start_validation_failure(tracked_wks_config, monkeypatch):
    """Test cmd_start with invalid backend."""
    # Use valid config so Pydantic passes, but mock validate_backend_type to fail
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.invalid", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    # Let's mock validate_backend_type to return False and update result
    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_start.cmd_start)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_start_not_installed(tracked_wks_config, monkeypatch):
    """Test cmd_start when service is not installed."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.foo", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    # Mock Service context manager and get_service_status
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = ServiceStatus(installed=False, unit_path="", running=False)

    # We mock Service class constructor to return a context manager that yields mock_service
    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.return_value = mock_service
    monkeypatch.setattr(cmd_start, "Service", mock_service_cls)

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Service is not installed" in result.result


def test_cmd_start_exception(tracked_wks_config, monkeypatch):
    """Test cmd_start when unexpected exception occurs."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.foo", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    # Mock __enter__ to raise default Exception
    mock_service_cls.return_value.__enter__.side_effect = Exception("Boom")
    monkeypatch.setattr(cmd_start, "Service", mock_service_cls)

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Error starting service: Boom" in result.result


def test_cmd_start_not_implemented_error(tracked_wks_config, monkeypatch):
    """Test cmd_start when NotImplementedError occurs."""
    tracked_wks_config.service = ServiceConfig(
        type="darwin",
        data={"label": "com.test.foo", "keep_alive": True, "run_at_load": False},  # type: ignore
    )

    mock_service_cls = MagicMock()
    mock_service_cls.return_value.__enter__.side_effect = NotImplementedError("Not supported")
    monkeypatch.setattr(cmd_start, "Service", mock_service_cls)

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Error: Service start not supported" in result.result
