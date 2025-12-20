"""Unit tests for wks.api.monitor.cmd_priority_add module."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_add
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def _make_monitor_config(**priority_dirs_override: float) -> MonitorConfig:
    """Helper to create MonitorConfig with optional priority dirs override."""
    return MonitorConfig.model_validate(
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
                "dirs": priority_dirs_override,
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


def test_cmd_priority_add_existing_returns_flag(tracked_wks_config):
    """Test cmd_priority_add when path already exists."""
    tracked_wks_config.monitor = _make_monitor_config(existing=1)

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="existing", priority=5)
    assert result.output["already_exists"] is True
    assert result.output["success"] is True
    assert tracked_wks_config.save_calls == 1


def test_cmd_priority_add_stores_and_saves(tracked_wks_config):
    """Test cmd_priority_add creates new priority directory and saves."""
    tracked_wks_config.monitor = _make_monitor_config()

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/new", priority=2)
    assert result.output["success"] is True
    assert result.output["created"] is True
    assert tracked_wks_config.save_calls == 1
    resolved = str(Path("/tmp/new").resolve())
    assert resolved in tracked_wks_config.monitor.priority.dirs
    assert tracked_wks_config.monitor.priority.dirs[resolved] == 2


def test_cmd_priority_add_not_found_creates(tracked_wks_config):
    """Test cmd_priority_add creates when path not found."""
    tracked_wks_config.monitor = _make_monitor_config()

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=5)
    assert result.output["success"] is True
    assert result.output["created"] is True
    resolved = str(Path("/tmp/a").resolve())
    assert tracked_wks_config.monitor.priority.dirs[resolved] == 5


def test_cmd_priority_add_updates(tracked_wks_config):
    """Test cmd_priority_add updates existing priority."""
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
                "dirs": {"/tmp/a": 1},
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

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert result.output["already_exists"] is True
    assert result.output["old_priority"] == 1
    assert result.output["new_priority"] == 7
    assert tracked_wks_config.monitor.priority.dirs["/tmp/a"] == 7
