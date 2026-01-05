"""Unit tests for monitor cmd_check (no mocks, real mongomock via config)."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor.cmd_check import cmd_check
from wks.api.URI import URI

pytestmark = pytest.mark.monitor


def test_cmd_check_reports_monitored(monkeypatch, tmp_path, minimal_config_dict):
    """Path under include_paths is monitored with computed priority.

    Requirements:
    - MON-001
    - MON-004
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    cfg["monitor"]["filter"]["include_paths"].append(str(watch_dir))
    target = watch_dir / "demo.txt"
    target.write_text("hi", encoding="utf-8")
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    assert result.output["is_monitored"] is True
    assert result.success is True
    assert result.output["priority"] is not None


def test_cmd_check_path_not_exists(monkeypatch, tmp_path, minimal_config_dict):
    """Nonexistent path outside include_paths is not monitored and fails.

    Requirements:
    - MON-001
    - MON-008
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    # No include paths -> default exclude
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    missing = tmp_path / "missing.txt"

    result = run_cmd(cmd_check, uri=URI.from_path(missing))

    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert result.success is False


def test_cmd_check_glob_exclusion(monkeypatch, tmp_path, minimal_config_dict):
    """Path matching exclude_globs reports '✗' symbol.

    Requirements:
    - MON-001
    - MON-004
    """
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    cfg["monitor"]["filter"]["include_paths"].append(str(watch_dir))
    cfg["monitor"]["filter"]["exclude_globs"] = ["*.tmp"]
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    target = watch_dir / "test.tmp"
    target.write_text("temp", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    assert result.output["is_monitored"] is False
    decision_symbols = [d["symbol"] for d in result.output["decisions"]]
    assert "✗" in decision_symbols


def test_cmd_check_empty_trace_fallback(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check handles empty trace gracefully (tests line 100)."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    # No include paths -> will be excluded with trace
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    missing = tmp_path / "missing.txt"

    result = run_cmd(cmd_check, uri=URI.from_path(missing))

    assert result.output["is_monitored"] is False
    # Should have fallback reason if trace is empty
    assert result.output["reason"] is not None
    assert result.success is False


def test_cmd_check_vault_uri_error(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check handles ValueError from vault URI path extraction."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Use vault URI which will fail path extraction without vault_path
    vault_uri = URI("vault:///nonexistent.md")
    result = run_cmd(cmd_check, uri=vault_uri)

    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert result.success is False
    assert len(result.output["decisions"]) == 0


def test_cmd_check_decision_symbols_various_trace_messages(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_check assigns correct symbols for various trace message types."""
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg = minimal_config_dict
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    cfg["monitor"]["filter"]["include_paths"].append(str(watch_dir))
    cfg["monitor"]["filter"]["include_dirnames"] = ["special"]
    cfg["monitor"]["filter"]["include_globs"] = ["*.special"]
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Test with override message (should get ✓)
    special_dir = watch_dir / "special"
    special_dir.mkdir()
    target = special_dir / "test.special"
    target.write_text("test", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    # Should have various symbols in decisions
    decision_symbols = [d["symbol"] for d in result.output["decisions"]]
    assert "✓" in decision_symbols or "•" in decision_symbols
