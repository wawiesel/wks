"""Unit tests for wks.api.monitor.cmd_priority_add module."""

from pathlib import Path

import pytest

from tests.unit.conftest import DummyConfig, run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor import cmd_priority_add

pytestmark = pytest.mark.monitor


def test_cmd_priority_add_existing_returns_flag(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"existing": 1}},
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

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="existing", priority=5)
    assert result.output["already_exists"] is True


def test_cmd_priority_add_stores_and_saves(monkeypatch):
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

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/new", priority=2)
    assert result.output["success"] is True
    resolved = str(Path("/tmp/new").resolve())
    assert resolved in cfg.monitor.priority.dirs


def test_cmd_priority_add_not_found_creates(monkeypatch):
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

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=5)
    assert result.output["success"] is True
    resolved = str(Path("/tmp/a").resolve())
    assert cfg.monitor.priority.dirs[resolved] == 5


def test_cmd_priority_add_updates(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 1}},
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

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert cfg.monitor.priority.dirs["/tmp/a"] == 7
