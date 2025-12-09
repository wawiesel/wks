"""Unit tests for wks.api.monitor.cmd_filter_show module."""

from types import SimpleNamespace

import pytest

from tests.unit.conftest import DummyConfig, run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor import cmd_filter_show

pytestmark = pytest.mark.monitor


def test_cmd_filter_show_lists_available_when_no_arg(monkeypatch):
    cfg = DummyConfig(SimpleNamespace())
    monkeypatch.setattr(WKSConfig, "load", lambda: cfg)

    result = run_cmd(cmd_filter_show.cmd_filter_show)
    assert result.output["available_lists"]
    assert result.output["success"] is True


def test_cmd_filter_show_returns_list(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": ["a", "b"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {
                    "dirs": {},
                    "weights": {
                        "depth_multiplier": 0.9,
                        "underscore_multiplier": 0.5,
                        "only_underscore_multiplier": 0.1,
                        "extension_weights": {},
                    },
                },
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
    monkeypatch.setattr(WKSConfig, "load", lambda: cfg)

    result = run_cmd(cmd_filter_show.cmd_filter_show, list_name="include_paths")
    assert result.output["count"] == 2
    assert "Showing" in result.result
    assert result.output["items"] == ["a", "b"]


def test_cmd_filter_show_unknown_list_name(monkeypatch):
    """Test cmd_filter_show with unknown list_name."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {
                    "include_paths": [],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {
                    "dirs": {},
                    "weights": {
                        "depth_multiplier": 0.9,
                        "underscore_multiplier": 0.5,
                        "only_underscore_multiplier": 0.1,
                        "extension_weights": {},
                    },
                },
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
    monkeypatch.setattr(WKSConfig, "load", lambda: cfg)

    with pytest.raises(ValueError):
        run_cmd(cmd_filter_show.cmd_filter_show, list_name="unknown_list")
