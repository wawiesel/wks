"""Unit tests for MonitorConfig public methods."""

import pytest
from wks.api.monitor.MonitorConfig import MonitorConfig
pytestmark = pytest.mark.monitor


def test_get_filter_list_names():
    """Test that get_filter_list_names returns all filter field names."""
    names = MonitorConfig.get_filter_list_names()
    assert "include_paths" in names
    assert "exclude_paths" in names
    assert "include_dirnames" in names
    assert "exclude_dirnames" in names
    assert "include_globs" in names
    assert "exclude_globs" in names
    assert len(names) == 6
    assert isinstance(names, tuple)


def test_get_rules():
    """Test that get_rules returns a dictionary of rule lists."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {
                    "include_paths": ["/tmp"],
                    "exclude_paths": ["/tmp/secret"],
                    "include_dirnames": ["src"],
                    "exclude_dirnames": ["node_modules"],
                    "include_globs": ["*.py"],
                    "exclude_globs": ["*.tmp"],
                },
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )
    
    rules = cfg.get_rules()
    assert isinstance(rules, dict)
    assert rules["include_paths"] == ["/tmp"]
    assert rules["exclude_paths"] == ["/tmp/secret"]
    assert rules["include_dirnames"] == ["src"]
    assert rules["exclude_dirnames"] == ["node_modules"]
    assert rules["include_globs"] == ["*.py"]
    assert rules["exclude_globs"] == ["*.tmp"]
    assert len(rules) == 6


def test_get_rules_empty():
    """Test that get_rules works with empty config."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )
    
    rules = cfg.get_rules()
    assert isinstance(rules, dict)
    assert all(rules[key] == [] for key in rules)


def test_from_config_dict_with_filter_section():
    """Test that from_config_dict flattens filter section."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {
                    "include_paths": ["/tmp"],
                },
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )
    
    assert cfg.include_paths == ["/tmp"]


def test_from_config_dict_without_filter_section():
    """Test that from_config_dict works without filter section."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "include_paths": ["/tmp"],
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )
    
    assert cfg.include_paths == ["/tmp"]


def test_from_config_dict_missing_monitor_section():
    """Test that from_config_dict raises KeyError when monitor section is missing."""
    try:
        MonitorConfig.from_config_dict({})
        assert False, "Should have raised KeyError"
    except KeyError as e:
        assert "monitor section is required" in str(e)

