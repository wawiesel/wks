from unittest.mock import MagicMock

import pytest

from tests.unit._service_test_helpers import build_darwin_service_config, patch_backend_import, patch_service_context
from tests.unit.conftest import run_cmd
from wks.api.service import cmd_stop
from wks.api.service.ServiceStatus import ServiceStatus

pytestmark = pytest.mark.daemon


def test_cmd_stop_not_installed(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(installed=False, unit_path="")
    patch_backend_import(monkeypatch, "darwin", mock_impl)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "not installed" in result.result.lower()
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_stop_success(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = ServiceStatus(installed=True, unit_path="/tmp/foo")
    mock_service.stop_service.return_value = {"success": True}
    patch_service_context(monkeypatch, cmd_stop, mock_service)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is True
    assert "Service stopped successfully" in result.result


def test_cmd_stop_already_stopped(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = ServiceStatus(installed=True, unit_path="/tmp/foo")
    mock_service.stop_service.return_value = {"success": True, "note": "already stopped"}
    patch_service_context(monkeypatch, cmd_stop, mock_service)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is True
    assert "Service is already stopped" in result.result


def test_cmd_stop_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_service = MagicMock()
    mock_service.get_service_status.return_value = ServiceStatus(installed=True, unit_path="/tmp/foo")
    mock_service.stop_service.return_value = {"success": False, "error": "Stop failed"}
    patch_service_context(monkeypatch, cmd_stop, mock_service)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error stopping service: Stop failed" in result.result


def test_cmd_stop_validation_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(cmd_stop.Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_stop_exception(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_stop, enter_side_effect=Exception("Boom"))

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error stopping service: Boom" in result.result


def test_cmd_stop_not_implemented(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_stop, enter_side_effect=NotImplementedError("Not supported"))

    result = run_cmd(cmd_stop.cmd_stop)
    assert result.success is False
    assert "Error: Service stop not supported" in result.result
