"""Unit tests for wks.api.monitor.cmd_priority_show module."""

# HODOR-ID: TST-MON-006-SHOW
# HODOR-REQS: MON-006
# HODOR-TEXT: Monitor priority show command returns expected output.
# HODOR-REF: tests/unit/test_wks_api_monitor_cmd_priority_show.py::test_cmd_priority_show_returns_stage_result

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_show
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_cmd_priority_show_returns_stage_result(tracked_wks_config, monkeypatch):
    """Test cmd_priority_show returns correct output."""
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
    assert result.output["count"] == 1
    assert result.output["priority_directories"] == {"/tmp/a": 1.0}
    assert "validation" in result.output
    assert result.success is True
