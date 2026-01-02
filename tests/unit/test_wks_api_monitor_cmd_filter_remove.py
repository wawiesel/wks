"""Unit tests for wks.api.monitor.cmd_filter_remove module."""

import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.monitor import cmd_filter_remove

pytestmark = pytest.mark.monitor


def test_cmd_filter_remove_saves_on_success(monkeypatch, tmp_path):
    # Isolate WKS_HOME for the tracked config
    h = tmp_path / "wks_home"
    h.mkdir()
    monkeypatch.setenv("WKS_HOME", str(h))

    # create_tracked_wks_config uses minimal_config_dict which already contains the transform cache in include_paths.
    # We add /tmp/x to it.
    cfg = create_tracked_wks_config(monkeypatch)
    cfg.monitor.filter.include_paths.append("/tmp/x")

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_not_found(monkeypatch, tmp_path):
    """Test cmd_filter_remove when value is not in the list."""
    h = tmp_path / "wks_home"
    h.mkdir()
    monkeypatch.setenv("WKS_HOME", str(h))
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_dirnames", value="nonexistent")
    assert result.success is False
    assert result.output["not_found"] is True
    assert "Value not found" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_remove_dirname_list(monkeypatch, tmp_path):
    """Test cmd_filter_remove with dirname list (non-path list)."""
    h = tmp_path / "wks_home"
    h.mkdir()
    monkeypatch.setenv("WKS_HOME", str(h))
    cfg = create_tracked_wks_config(monkeypatch)
    cfg.monitor.filter.include_dirnames.append("testdir")

    result = run_cmd(cmd_filter_remove.cmd_filter_remove, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_remove_unknown_list(monkeypatch, tmp_path):
    """Unknown list names should produce a validation error and halt."""
    h = tmp_path / "wks_home"
    h.mkdir()
    monkeypatch.setenv("WKS_HOME", str(h))
    create_tracked_wks_config(monkeypatch)

    result = cmd_filter_remove.cmd_filter_remove(list_name="not_a_list", value="x")
    with pytest.raises(ValueError):
        list(result.progress_callback(result))
    assert result.success is False
    assert "Unknown list_name" in result.output["errors"][0]
