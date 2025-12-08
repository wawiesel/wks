"""Unit tests for wks.api.monitor.cmd_priority_show module."""


import pytest

from tests.unit.conftest import DummyConfig, run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor import cmd_priority_show

pytestmark = pytest.mark.monitor


def test_cmd_priority_show_returns_stage_result(monkeypatch):
    from wks.api.monitor.MonitorConfig import MonitorConfig

    monitor_cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {},
                "priority": {"dirs": {"/tmp/a": 1.0}},
                "database": "monitor",
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

    # Mock explain_path to return True
    monkeypatch.setattr("wks.api.monitor.cmd_priority_show.explain_path", lambda _cfg, _path: (True, []))

    result = run_cmd(cmd_priority_show.cmd_priority_show, )
    assert result.output["count"] == 1
