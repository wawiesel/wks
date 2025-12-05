"""Unit tests for wks.api.monitor.cmd_check module."""

import pytest
from types import SimpleNamespace

from wks.api.monitor import cmd_check
from tests.unit.conftest import DummyConfig
pytestmark = pytest.mark.monitor


def test_cmd_check_reports_monitored(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Mock explain_path to return True
    monkeypatch.setattr("wks.api.monitor.cmd_check.explain_path", lambda _cfg, _path: (True, ["Included by rule"]))
    monkeypatch.setattr(
        "wks.api.monitor.cmd_check.calculate_priority",
        lambda _path, _dirs, _weights: 5,
    )

    result = cmd_check.cmd_check(path="/tmp/demo.txt")
    assert result.output["is_monitored"] is True
    assert "priority" in result.result

def test_cmd_check_path_not_exists(monkeypatch):
    """Test cmd_check when path doesn't exist."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}, "weights": {}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Mock explain_path to return False
    monkeypatch.setattr("wks.api.monitor.cmd_check.explain_path", lambda _cfg, _path: (False, ["Excluded by rule"]))

    result = cmd_check.cmd_check(path="/nonexistent/path.txt")
    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert "⚠" in result.output["decisions"][0]["symbol"]  # Path doesn't exist symbol
