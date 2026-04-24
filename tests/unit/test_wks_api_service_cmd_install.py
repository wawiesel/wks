from unittest.mock import MagicMock

import pytest

from tests.unit._service_test_helpers import build_darwin_service_config, patch_backend_import, patch_service_context
from tests.unit.conftest import run_cmd
from wks.api.service import cmd_install

pytestmark = pytest.mark.daemon


def test_cmd_install_success(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_impl = MagicMock()
    mock_impl.install_service.return_value = {
        "success": True,
        "label": "com.test.wks",
        "plist_path": "/path/to/plist",
    }
    patch_backend_import(monkeypatch, "darwin", mock_impl)

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_install_validation_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()

    def mock_validate(res_obj, *args):
        res_obj.success = False
        res_obj.result = "Validation failed"
        return False

    monkeypatch.setattr(cmd_install.Service, "validate_backend_type", mock_validate)

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is False
    assert result.result == "Validation failed"


def test_cmd_install_failure(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    mock_service = MagicMock()
    mock_service.install_service.return_value = {"success": False, "error": "Install failed"}
    patch_service_context(monkeypatch, cmd_install, mock_service)

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is False
    assert result.result == "Install failed"


def test_cmd_install_exception(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_install, enter_side_effect=Exception("Boom"))

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is False
    assert "Error installing service: Boom" in result.result


def test_cmd_install_not_implemented(tracked_wks_config, monkeypatch):
    tracked_wks_config.service = build_darwin_service_config()
    patch_service_context(monkeypatch, cmd_install, enter_side_effect=NotImplementedError("Not supported"))

    result = run_cmd(cmd_install.cmd_install)
    assert result.success is False
    assert "Error: Service installation not supported" in result.result
