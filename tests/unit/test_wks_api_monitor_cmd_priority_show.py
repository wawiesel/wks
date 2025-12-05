"""Unit tests for wks.api.monitor.cmd_priority_show module."""

import pytest
from types import SimpleNamespace

from wks.api.monitor import cmd_priority_show
from tests.unit.conftest import DummyConfig
pytestmark = pytest.mark.monitor


def test_cmd_priority_show_returns_stage_result(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 1.0}},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    cfg = DummyConfig(monitor_cfg)
    monkeypatch.setattr("wks.config.WKSConfig.load", lambda: cfg)

    # Mock explain_path to return True
    monkeypatch.setattr("wks.api.monitor.cmd_priority_show.explain_path", lambda _cfg, _path: (True, []))

    result = cmd_priority_show.cmd_priority_show()
    assert result.output["count"] == 1
