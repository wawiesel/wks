"""Unit tests for wks.api.monitor.cmd_priority_show module."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_show
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_cmd_priority_show_returns_stage_result(patch_wks_config, monkeypatch):
    """Test cmd_priority_show returns correct output."""
    patch_wks_config.monitor = MonitorConfig(
        filter={},
        priority={"dirs": {"/tmp/a": 1.0}},
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    # Mock explain_path to return True
    monkeypatch.setattr("wks.api.monitor.cmd_priority_show.explain_path", lambda _cfg, _path: (True, []))

    result = run_cmd(cmd_priority_show.cmd_priority_show)
    assert result.output["count"] == 1
    assert result.output["priority_directories"] == {"/tmp/a": 1.0}
    assert "validation" in result.output
    assert result.success is True
