"""Unit tests for wks.api.monitor.cmd_filter_show module (real config)."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor import cmd_filter_show

pytestmark = pytest.mark.monitor


def test_cmd_filter_show_lists_available_when_no_arg(monkeypatch, tmp_path, minimal_config_dict):
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    result = run_cmd(cmd_filter_show.cmd_filter_show)
    assert result.output["available_lists"]
    assert result.success is True


def test_cmd_filter_show_returns_list(monkeypatch, tmp_path, minimal_config_dict):
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    cfg = minimal_config_dict
    cfg["monitor"]["filter"]["include_paths"] = ["a", "b"]
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_filter_show.cmd_filter_show, list_name="include_paths")
    assert result.output["count"] == 2
    assert "Showing" in result.result

    from wks.utils.normalize_path import normalize_path

    expected = [str(normalize_path("a")), str(normalize_path("b"))]
    assert result.output["items"] == expected


def test_cmd_filter_show_unknown_list_name(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_filter_show with unknown list_name."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    with pytest.raises(ValueError):
        run_cmd(cmd_filter_show.cmd_filter_show, list_name="unknown_list")
