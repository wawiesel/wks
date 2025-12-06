"""Unit tests for wks.api.monitor.cmd_priority_add module."""


import pytest

from tests.unit.conftest import DummyConfig
from wks.api.monitor import cmd_priority_add

pytestmark = pytest.mark.monitor


def test_cmd_priority_add_existing_returns_flag(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"existing": 1}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_add.cmd_priority_add(path="existing", priority=5)
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 1


def test_cmd_priority_add_stores_and_saves(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/new", priority=2)
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/new" in cfg.monitor.priority.dirs


def test_cmd_priority_add_not_found_creates(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/a", priority=5)
    assert result.output["success"] is True
    assert cfg.monitor.priority.dirs["/tmp/a"] == 5
    assert cfg.save_calls == 1


def test_cmd_priority_add_updates(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 1}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_add.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_add.cmd_priority_add(path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert cfg.monitor.priority.dirs["/tmp/a"] == 7
    assert cfg.save_calls == 1
