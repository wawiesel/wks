"""Unit tests for wks.api.monitor.MonitorConfig module."""

import pytest
from pydantic import ValidationError

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


def test_monitor_config_from_config_dict_missing():
    """Reject missing monitor config section.

    Requirements:
    - MON-001
    """
    with pytest.raises(KeyError, match="monitor section is required"):
        MonitorConfig.from_config_dict({})


def test_monitor_config_from_config_dict_invalid():
    """Reject invalid monitor config values.

    Requirements:
    - MON-001
    """
    raw = {"monitor": {"max_documents": -1}}
    with pytest.raises(ValidationError):
        MonitorConfig.from_config_dict(raw)


def test_monitor_config_get_rules():
    cfg = MonitorConfig.model_validate(
        {
            "filter": {
                "include_paths": ["/src"],
                "exclude_paths": ["/node_modules"],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
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
    rules = cfg.get_rules()
    assert rules["include_paths"] == ["/src"]
    assert rules["exclude_paths"] == ["/node_modules"]
    assert "include_dirnames" in rules
