"""Unit tests for wks.api.monitor.cmd_priority_add module."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_priority_add
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_cmd_priority_add_existing_returns_flag(patch_wks_config):
    """Test cmd_priority_add when path already exists."""
    patch_wks_config.monitor = MonitorConfig(
        filter={},
        priority={"dirs": {"existing": 1}},
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="existing", priority=5)
    assert result.output["already_exists"] is True
    assert result.output["success"] is True
    assert patch_wks_config.save_calls == 1


def test_cmd_priority_add_stores_and_saves(patch_wks_config):
    """Test cmd_priority_add creates new priority directory and saves."""
    patch_wks_config.monitor = MonitorConfig(
        filter={},
        priority={"dirs": {}},
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/new", priority=2)
    assert result.output["success"] is True
    assert result.output["created"] is True
    assert patch_wks_config.save_calls == 1
    resolved = str(Path("/tmp/new").resolve())
    assert resolved in patch_wks_config.monitor.priority.dirs
    assert patch_wks_config.monitor.priority.dirs[resolved] == 2


def test_cmd_priority_add_not_found_creates(patch_wks_config):
    """Test cmd_priority_add creates when path not found."""
    patch_wks_config.monitor = MonitorConfig(
        filter={},
        priority={"dirs": {}},
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=5)
    assert result.output["success"] is True
    assert result.output["created"] is True
    resolved = str(Path("/tmp/a").resolve())
    assert patch_wks_config.monitor.priority.dirs[resolved] == 5


def test_cmd_priority_add_updates(patch_wks_config):
    """Test cmd_priority_add updates existing priority."""
    patch_wks_config.monitor = MonitorConfig(
        filter={},
        priority={"dirs": {"/tmp/a": 1}},
        database="monitor",
        sync={"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
    )

    result = run_cmd(cmd_priority_add.cmd_priority_add, path="/tmp/a", priority=7)
    assert result.output["success"] is True
    assert result.output["already_exists"] is True
    assert result.output["old_priority"] == 1
    assert result.output["new_priority"] == 7
    assert patch_wks_config.monitor.priority.dirs["/tmp/a"] == 7
