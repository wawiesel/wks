"""Unit tests for wks.api.monitor.cmd_priority_show module."""

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_show
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_cmd_priority_show_returns_stage_result(tracked_wks_config, monkeypatch):
    """Test cmd_priority_show returns correct output.

    Requirements:
    - MON-001
    - MON-007
    """
    tracked_wks_config.monitor = MonitorConfig.model_validate(
        {
            "filter": {
                "include_paths": [],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
            },
            "priority": {
                "dirs": {"/tmp/a": 1.0},
                "weights": {
                    "depth_multiplier": 0.9,
                    "underscore_multiplier": 0.5,
                    "only_underscore_multiplier": 0.1,
                    "extension_weights": {},
                },
            },
            "max_documents": 1000000,
            "min_priority": 0.0,
            "remote": {"mappings": []},
        }
    )

    # Mock explain_path to return True
    monkeypatch.setattr("wks.api.monitor.cmd_priority_show.explain_path", lambda _cfg, _path: (True, []))

    result = run_cmd(cmd_priority_show.cmd_priority_show)
    assert result.success is True
    assert set(result.output.keys()) == {"errors", "warnings", "priority_directories", "count", "validation"}
    assert result.output["errors"] == []
    assert result.output["warnings"] == []
    assert result.output["count"] == 1
    assert result.output["priority_directories"] == {"/tmp/a": 1.0}
    assert "/tmp/a" in result.output["validation"]
    assert result.output["validation"]["/tmp/a"]["priority"] == 1.0
    assert result.output["validation"]["/tmp/a"]["valid"] is True
    assert result.output["validation"]["/tmp/a"]["error"] is None
