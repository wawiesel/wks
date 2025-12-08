"""Unit tests for wks.api.monitor.cmd_priority_remove module."""


import pytest

from tests.unit.conftest import DummyConfig
from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor import cmd_priority_remove

pytestmark = pytest.mark.monitor


def test_cmd_priority_remove_not_found(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {}},
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

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/miss")
    assert result.output["not_found"] is True
    assert cfg.save_calls == 0


def test_cmd_priority_remove_success(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 3}},
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

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/a")
    assert result.output["success"] is True
    assert cfg.save_calls == 1
    assert "/tmp/a" not in cfg.monitor.priority.dirs
