from unittest.mock import MagicMock

import pytest

from tests.unit._service_test_helpers import build_darwin_service_config, patch_backend_import, patch_service_context
from tests.unit.conftest import run_cmd
from wks.api.service import cmd_uninstall

pytestmark = pytest.mark.daemon


def test_cmd_uninstall_success(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_impl = MagicMock()
    mock_impl.uninstall_service.return_value = {
        "success": True,
        "label": "com.test.wks",
    }
    patch_backend_import(monkeypatch, "darwin", mock_impl)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_uninstall_validation_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(cmd_uninstall.Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_uninstall_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_service = MagicMock()
    mock_service.uninstall_service.return_value = {"success": False, "error": "Uninstall failed"}
    patch_service_context(monkeypatch, cmd_uninstall, mock_service)

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert result.result == "Uninstall failed"


def test_cmd_uninstall_exception(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_uninstall, enter_side_effect=Exception("Boom"))

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert "Error uninstalling service: Boom" in result.result


def test_cmd_uninstall_not_implemented(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_uninstall, enter_side_effect=NotImplementedError("Not supported"))

    result = run_cmd(cmd_uninstall.cmd_uninstall)
    assert result.success is False
    assert "Error: Service uninstallation not supported" in result.result
