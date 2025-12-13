"""Unit tests for wks.api.monitor.cmd_filter_remove module."""

import pytest

from tests.unit.conftest import create_patched_config, run_cmd
from wks.api.monitor import cmd_filter_remove

pytestmark = pytest.mark.monitor


def test_cmd_filter_remove_saves_on_success(monkeypatch):
    cfg = create_patched_config(monkeypatch, {"filter": {"include_paths": ["/tmp/x"]}})

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_not_found(monkeypatch):
    """Test cmd_filter_remove when value is not in the list."""
    cfg = create_patched_config(monkeypatch)

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_dirnames", value="nonexistent")
    assert result.success is False
    assert result.output["not_found"] is True
    assert "Value not found" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_remove_dirname_list(monkeypatch):
    """Test cmd_filter_remove with dirname list (non-path list)."""
    cfg = create_patched_config(monkeypatch, {"filter": {"include_dirnames": ["testdir"]}})

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_unknown_list(monkeypatch):
    """Unknown list names should produce a validation error and halt."""
    create_patched_config(monkeypatch)

    result = cmd_filter_remove.cmd_filter_remove(list_name="not_a_list", value="x")
    with pytest.raises(ValueError):
        list(result.progress_callback(result))
    assert result.success is False
    assert "Unknown list_name" in result.output["errors"][0]
