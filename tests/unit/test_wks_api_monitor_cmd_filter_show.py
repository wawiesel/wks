"""Unit tests for wks.api.monitor.cmd_filter_show module."""

from types import SimpleNamespace

import pytest

from tests.unit.conftest import DummyConfig
from wks.api.monitor import cmd_filter_show

pytestmark = pytest.mark.monitor


def test_cmd_filter_show_lists_available_when_no_arg(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr("wks.api.monitor.cmd_filter_show.WKSConfig.load", lambda: cfg)

    result = cmd_filter_show.cmd_filter_show()
    assert result.output["available_lists"]
    assert result.output["success"] is True


def test_cmd_filter_show_returns_list(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": ["a", "b"]},
                "priority": {},
                "database": "monitor",
                "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_filter_show.WKSConfig.load", lambda: cfg)

    result = cmd_filter_show.cmd_filter_show(list_name="include_paths")
    assert result.output["count"] == 2
    assert "Showing" in result.result
    assert result.output["items"] == ["a", "b"]


def test_cmd_filter_show_unknown_list_name(monkeypatch):
    """Test cmd_filter_show with unknown list_name."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {},
                "database": "monitor",
                "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_filter_show.WKSConfig.load", lambda: cfg)

    try:
        cmd_filter_show.cmd_filter_show(list_name="unknown_list")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown list_name" in str(e)
