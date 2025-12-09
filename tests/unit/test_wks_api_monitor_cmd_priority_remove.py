"""Unit tests for wks.api.monitor.cmd_priority_remove module."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_remove
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_cmd_priority_remove_not_found(patch_wks_config):
    """Test cmd_priority_remove when path not found."""
    patch_wks_config.monitor = MonitorConfig(
        filter={
            "include_paths": [],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
        },
        priority={
            "dirs": {},
            "weights": {
                "depth_multiplier": 0.9,
                "underscore_multiplier": 0.5,
                "only_underscore_multiplier": 0.1,
                "extension_weights": {},
            },
        },
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/miss")
    assert result.output["not_found"] is True
    assert result.output["success"] is False
    assert patch_wks_config.save_calls == 0


def test_cmd_priority_remove_success(patch_wks_config):
    """Test cmd_priority_remove successfully removes priority directory."""
    patch_wks_config.monitor = MonitorConfig(
        filter={
            "include_paths": [],
            "exclude_paths": [],
            "include_dirnames": [],
            "exclude_dirnames": [],
            "include_globs": [],
            "exclude_globs": [],
        },
        priority={
            "dirs": {"/tmp/a": 3},
            "weights": {
                "depth_multiplier": 0.9,
                "underscore_multiplier": 0.5,
                "only_underscore_multiplier": 0.1,
                "extension_weights": {},
            },
        },
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/a")
    assert result.output["success"] is True
    assert patch_wks_config.save_calls == 1
    resolved = str(Path("/tmp/a").resolve())
    assert resolved not in patch_wks_config.monitor.priority.dirs
