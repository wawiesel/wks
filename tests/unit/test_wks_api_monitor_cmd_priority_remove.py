"""Unit tests for wks.api.monitor.cmd_priority_remove module."""


import pytest

from tests.unit.conftest import DummyConfig
from wks.api.monitor import cmd_priority_remove

pytestmark = pytest.mark.monitor


def test_cmd_priority_remove_not_found(monkeypatch):
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
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.find_matching_path_key", lambda mapping, path: None)

    result = cmd_priority_remove.cmd_priority_remove(path="/tmp/miss")
    assert result.output["not_found"] is True
    assert cfg.save_calls == 0


def test_cmd_priority_remove_success(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 3}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.canonicalize_path", lambda p: p)
    monkeypatch.setattr("wks.api.monitor.cmd_priority_remove.find_matching_path_key", lambda mapping, path: path)

    result = cmd_priority_remove.cmd_priority_remove(path="/tmp/a")
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/a" not in cfg.monitor.priority.dirs
