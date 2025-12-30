"""Unit tests for wks.api.monitor.MonitorConfig module."""

from wks.api.monitor.MonitorConfig import MonitorConfig


def test_monitor_config_valid():
    cfg = MonitorConfig.model_validate(
        {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": ["*.md"],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {},
                "weights": {
                    "depth_multiplier": 1.0,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "remote": {"mappings": []},
            "max_documents": 1000,
            "min_priority": 1.0,
        }
    )
    assert cfg.filter.include_globs == ["*.md"]
    assert cfg.priority.weights.depth_multiplier == 1.0


def test_monitor_config_from_config_dict():
    raw = {
        "monitor": {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": ["*.md"],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {},
                "weights": {
                    "depth_multiplier": 1.0,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "remote": {"mappings": []},
            "max_documents": 1000,
            "min_priority": 1.0,
        }
    }
    cfg = MonitorConfig.from_config_dict(raw)
    assert cfg.max_documents == 1000
