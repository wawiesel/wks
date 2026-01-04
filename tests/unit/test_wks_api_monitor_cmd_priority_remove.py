"""Unit tests for wks.api.monitor.cmd_priority_remove module."""

import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.monitor import cmd_priority_remove

pytestmark = pytest.mark.monitor


def test_cmd_priority_remove_not_found(monkeypatch):
    """Test cmd_priority_remove with non-existent path.

    Requirements:
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)
    cfg.monitor.priority.dirs = {"/tmp/existing": 10.0}

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/nonexistent")
    assert result.success is False
    assert result.output["not_found"] is True
    assert "Not a priority directory" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_priority_remove_success(monkeypatch):
    """Test cmd_priority_remove success.

    Requirements:
    - MON-006
    """
    path = "/tmp/test"
    resolved = path  # canonicalize_path returns same path on unix if no ~

    cfg = create_tracked_wks_config(monkeypatch)
    cfg.monitor.priority.dirs = {resolved: 100.0}

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path=path)
    assert result.success is True
    assert result.output["path_removed"] == resolved
    assert result.output["priority"] == 100.0
    assert cfg.save_calls == 1
    assert resolved not in cfg.monitor.priority.dirs


def test_cmd_priority_remove_empty_list(monkeypatch):
    """Test cmd_priority_remove with empty priority list.

    Requirements:
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_priority_remove.cmd_priority_remove, path="/tmp/test")
    assert result.success is False
    assert result.output["not_found"] is True
    assert "No priority directories configured" in result.output["message"]
    assert cfg.save_calls == 0
