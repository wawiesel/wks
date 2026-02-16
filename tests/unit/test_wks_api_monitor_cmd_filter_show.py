"""Unit tests for wks.api.monitor.cmd_filter_show module (real config)."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_filter_show

pytestmark = pytest.mark.monitor


def test_cmd_filter_show_lists_available_when_no_arg(monkeypatch, tmp_path, minimal_config_dict):
    """Lists available filter sets when no list name is provided.

    Requirements:
    - MON-001
    - MON-006
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(cmd_filter_show.cmd_filter_show)
    assert result.success is True
    assert set(result.output.keys()) == {"errors", "warnings", "list_name", "available_lists", "items", "count"}
    assert result.output["errors"] == []
    assert result.output["warnings"] == []
    assert result.output["available_lists"]
    assert result.output["items"] == []
    assert result.output["count"] == 0
    assert result.output["list_name"] is None


def test_cmd_filter_show_returns_list(monkeypatch, tmp_path, minimal_config_dict):
    """Returns the requested filter list.

    Requirements:
    - MON-001
    - MON-006
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    cfg["monitor"]["filter"]["include_paths"].extend(["a", "b"])
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_filter_show.cmd_filter_show, list_name="include_paths")
    assert result.success is True
    assert set(result.output.keys()) == {"errors", "warnings", "list_name", "available_lists", "items", "count"}
    assert result.output["errors"] == []
    assert result.output["warnings"] == []
    assert result.output["list_name"] == "include_paths"
    # minimal_config_dict has 2 paths (default + isolated cache) + 2 from extend = 4
    assert result.output["count"] == 4
    assert "Showing" in result.result

    from wks.api.config.normalize_path import normalize_path

    # Sort to avoid ordering issues if any
    items = sorted(result.output["items"])
    # Should include "a", "b", the isolated cache dir, AND the default "/tmp/wks_test_transform"
    expected = sorted(
        [
            str(normalize_path("a")),
            str(normalize_path("b")),
            cfg["transform"]["cache"]["base_dir"],
            str(normalize_path("/tmp/wks_test_transform")),
        ]
    )
    assert items == expected


def test_cmd_filter_show_unknown_list_name(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_filter_show with unknown list_name.

    Requirements:
    - MON-001
    - MON-006
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    with pytest.raises(ValueError):
        run_cmd(cmd_filter_show.cmd_filter_show, list_name="unknown_list")
