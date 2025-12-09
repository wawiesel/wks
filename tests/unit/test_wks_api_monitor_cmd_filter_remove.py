"""Unit tests for wks.api.monitor.cmd_filter_remove module."""


import pytest

from tests.unit.conftest import DummyConfig
from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor import cmd_filter_remove

pytestmark = pytest.mark.monitor


def test_cmd_filter_remove_saves_on_success(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": ["/tmp/x"],
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

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_not_found(monkeypatch):
    """Test cmd_filter_remove when value not found."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": [],
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

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is False
    assert "not_found" in result.output
    assert cfg.save_calls == 0


def test_cmd_filter_remove_dirname_list(monkeypatch):
    """Test cmd_filter_remove with dirname list (non-path list, hits line 25)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_dirnames": ["testdir"],
                    "include_paths": [],
                    "exclude_paths": [],
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

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1
