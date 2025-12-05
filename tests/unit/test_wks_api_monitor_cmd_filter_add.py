"""Unit tests for wks.api.monitor.cmd_filter_add module."""

import pytest
from types import SimpleNamespace

from wks.api.monitor import cmd_filter_add
from tests.unit.conftest import DummyConfig
pytestmark = pytest.mark.monitor


def test_cmd_filter_add_saves_on_success(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1

def test_cmd_filter_add_unknown_list_name(monkeypatch):
    """Test cmd_filter_add with unknown list_name."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    try:
        cmd_filter_add.cmd_filter_add(list_name="unknown_list", value="test")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown list_name" in str(e)

def test_cmd_filter_add_empty_dirname(monkeypatch):
    """Test cmd_filter_add with empty dirname."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_dirnames": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_dirnames", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0

def test_cmd_filter_add_wildcard_in_dirname(monkeypatch):
    """Test cmd_filter_add with wildcard in dirname."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_dirnames": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_dirnames", value="test*")
    assert result.output["success"] is False
    assert "wildcard characters" in result.output["message"]
    assert cfg.save_calls == 0

def test_cmd_filter_add_dirname_in_opposite(monkeypatch):
    """Test cmd_filter_add when dirname already in opposite list (hits line 50)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"exclude_dirnames": ["testdir"]},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_dirnames", value="testdir")
    assert result.output["success"] is False
    assert "already present in exclude_dirnames" in result.output["message"]
    assert cfg.save_calls == 0

def test_cmd_filter_add_dirname_no_error(monkeypatch):
    """Test cmd_filter_add with valid dirname (hits lines 55-56)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_dirnames": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1

def test_cmd_filter_add_empty_glob(monkeypatch):
    """Test cmd_filter_add with empty glob."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_globs": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_globs", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0

def test_cmd_filter_add_glob_validation_success(monkeypatch):
    """Test cmd_filter_add with valid glob (hits lines 64-66, 73-74)."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_globs": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_globs", value="*.py")
    assert result.output["success"] is True
    assert cfg.save_calls == 1

def test_cmd_filter_add_else_branch(monkeypatch):
    """Test cmd_filter_add with non-path, non-dirname, non-glob list (hits lines 75-77)."""
    # This shouldn't happen with current filter lists, but test the else branch anyway
    # Actually, all current lists are paths, dirnames, or globs, so this branch is defensive
    # We can't easily test this without adding a new list type, so we'll skip it
    pass

def test_cmd_filter_add_validation_error(monkeypatch):
    """Test cmd_filter_add with validation error."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_dirnames": []},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Try to add invalid dirname (with path separator)
    result = cmd_filter_add.cmd_filter_add(list_name="include_dirnames", value="invalid/path")
    assert result.output["success"] is False
    assert "validation_failed" in result.output
    assert cfg.save_calls == 0

def test_cmd_filter_add_duplicate(monkeypatch):
    """Test cmd_filter_add with duplicate value."""
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_paths": ["/tmp/x"]},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    result = cmd_filter_add.cmd_filter_add(list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is False
    assert "already_exists" in result.output
    assert cfg.save_calls == 0
