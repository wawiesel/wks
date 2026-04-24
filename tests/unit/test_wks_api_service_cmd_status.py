import json
from unittest.mock import MagicMock

import pytest

from tests.unit._service_test_helpers import build_darwin_service_config, patch_backend_import
from tests.unit.conftest import run_cmd
from wks.api.log.summarize_status_log_messages import STATUS_LOG_MESSAGE_LIMIT
from wks.api.service import cmd_status
from wks.api.service.ServiceStatus import ServiceStatus

pytestmark = pytest.mark.daemon


def test_cmd_status_success(tracked_wks_config, monkeypatch, tmp_path):
    tracked_wks_config.service = build_darwin_service_config()

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=True,
        running=True,
        pid=12345,
        unit_path="/tmp/test.plist",
    )
    patch_backend_import(monkeypatch, "darwin", mock_impl)
    monkeypatch.setattr(cmd_status, "_pid_running", lambda pid: True)

    result = run_cmd(cmd_status.cmd_status)
    assert result.success is True
    assert result.output["running"] is True
    assert result.output["installed"] is True
    assert result.output["pid"] == 12345
    assert result.output["log_path"].endswith("logfile")
    assert "errors" in result.output and result.output["errors"] == []
    assert "warnings" in result.output and result.output["warnings"] == []


def test_cmd_status_not_installed(tracked_wks_config, monkeypatch, tmp_path):
    tracked_wks_config.service = build_darwin_service_config()

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=False,
        unit_path="",
    )
    patch_backend_import(monkeypatch, "darwin", mock_impl)

    result = run_cmd(cmd_status.cmd_status)
    assert result.success is True
    assert result.output["running"] is False
    assert result.output["installed"] is False
    assert result.output["log_path"].endswith("logfile")
    assert "errors" in result.output and result.output["errors"] == []
    assert "warnings" in result.output and result.output["warnings"] == []


def test_cmd_status_summarizes_large_daemon_message_lists(tracked_wks_config, monkeypatch, tmp_path):
    tracked_wks_config.service = build_darwin_service_config()

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: tmp_path))

    warnings = [f"warn-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 4)]
    errors = [f"error-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 2)]
    (tmp_path / "daemon.json").write_text(
        json.dumps({"warnings": warnings, "errors": errors, "pid": 12345}),
        encoding="utf-8",
    )

    mock_impl = MagicMock()
    mock_impl.get_service_status.return_value = ServiceStatus(
        installed=True,
        running=True,
        pid=12345,
        unit_path="/tmp/test.plist",
    )
    patch_backend_import(monkeypatch, "darwin", mock_impl)
    monkeypatch.setattr(cmd_status, "_pid_running", lambda pid: True)

    result = run_cmd(cmd_status.cmd_status)

    assert result.success is True
    assert len(result.output["warnings"]) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert len(result.output["errors"]) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert "showing 20 most recent warnings out of 24 total" in result.output["warnings"][0]
    assert "showing 20 most recent errors out of 22 total" in result.output["errors"][0]
    assert result.output["warnings"][1:] == warnings[-STATUS_LOG_MESSAGE_LIMIT:]
    assert result.output["errors"][1:] == errors[-STATUS_LOG_MESSAGE_LIMIT:]
