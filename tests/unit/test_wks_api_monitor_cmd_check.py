"""Unit tests for monitor cmd_check (no mocks, real mongomock via config)."""

import json
from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor.cmd_check import cmd_check

pytestmark = pytest.mark.monitor


def test_cmd_check_reports_monitored(monkeypatch, tmp_path, minimal_config_dict):
    """Path under include_paths is monitored with computed priority."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    cfg["monitor"]["filter"]["include_paths"] = [str(watch_dir)]
    target = watch_dir / "demo.txt"
    target.write_text("hi", encoding="utf-8")
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, path=str(target))

    assert result.output["is_monitored"] is True
    assert result.success is True
    assert result.output["priority"] is not None


def test_cmd_check_path_not_exists(monkeypatch, tmp_path, minimal_config_dict):
    """Nonexistent path outside include_paths is not monitored and fails."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    # No include paths -> default exclude
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    missing = tmp_path / "missing.txt"

    result = run_cmd(cmd_check, path=str(missing))

    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert result.success is False


def test_cmd_check_other_trace_message(monkeypatch, tmp_path, minimal_config_dict):
    """Trace message without included/excluded prefix uses bullet symbol."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    # Empty include_paths to trigger default exclude trace
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    target = tmp_path / "test.txt"
    target.write_text("data", encoding="utf-8")

    result = run_cmd(cmd_check, path=str(target))

    decision_symbols = [d["symbol"] for d in result.output["decisions"]]
    assert "•" in decision_symbols
    assert result.output["is_monitored"] is False
