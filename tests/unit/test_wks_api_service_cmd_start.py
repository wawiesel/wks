from unittest.mock import MagicMock

import pytest

from tests.unit._service_test_helpers import build_darwin_service_config, patch_backend_import, patch_service_context
from tests.unit.conftest import run_cmd
from wks.api.service import ServiceStartOutput, cmd_start
from wks.api.service.Service import Service
from wks.api.service.ServiceStatus import ServiceStatus

pytestmark = pytest.mark.daemon


def test_cmd_start_success(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=True, unit_path="/tmp/test.plist", running=False
    )
    mock_impl.start_service.return_value = {"success": True, "label": "com.test.wks"}
    patch_backend_import(monkeypatch, "darwin", mock_impl)
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


def test_cmd_start_warns_when_already_running(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=True, unit_path="/tmp/test.plist", running=True, pid=9999
    )
    mock_impl.start_service.return_value = {"success": True, "label": "com.test.wks"}
    patch_backend_import(monkeypatch, "darwin", mock_impl)
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
    assert "already running" in result.result
    assert any("already running" in w for w in result.output["warnings"])


def test_cmd_start_validation_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config(label="com.test.invalid")

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_start.cmd_start)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_start_not_installed(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config(label="com.test.foo")
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = ServiceStatus(installed=False, unit_path="", running=False)
    patch_service_context(monkeypatch, cmd_start, mock_service)

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Service is not installed" in result.result


def test_cmd_start_exception(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config(label="com.test.foo")
    patch_service_context(monkeypatch, cmd_start, enter_side_effect=Exception("Boom"))

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Error starting service: Boom" in result.result


def test_cmd_start_not_implemented_error(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config(label="com.test.foo")
    patch_service_context(monkeypatch, cmd_start, enter_side_effect=NotImplementedError("Not supported"))

    result = run_cmd(cmd_start.cmd_start)

    assert result.success is False
    assert "Error: Service start not supported" in result.result
