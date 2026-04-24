import copy
import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.monitor.cmd_check import cmd_check

pytestmark = pytest.mark.monitor


def setup_monitor_check_env(monkeypatch, tmp_path, minimal_config_dict, *, include_watch=True, **filter_updates):
    wks_home = tmp_path / "wks_home"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    config = copy.deepcopy(minimal_config_dict)
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    if include_watch:
        config["monitor"]["filter"]["include_paths"].append(str(watch_dir))
    config["monitor"]["filter"].update(filter_updates)
    (wks_home / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return watch_dir


def test_cmd_check_reports_monitored(monkeypatch, tmp_path, minimal_config_dict):
    """Requirements:
    - MON-001
    - MON-004"""
    watch_dir = setup_monitor_check_env(monkeypatch, tmp_path, minimal_config_dict)
    target = watch_dir / "demo.txt"
    target.write_text("hi", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    assert result.success is True
    assert result.output["is_monitored"] is True
    assert result.output["priority"] is not None


@pytest.mark.parametrize(
    "uri_factory", [lambda root: root / "missing.txt", lambda root: URI("vault:///nonexistent.md")]
)
def test_cmd_check_reports_unmonitored_target(monkeypatch, tmp_path, minimal_config_dict, uri_factory):
    """Requirements:
    - MON-001
    - MON-008"""
    watch_dir = setup_monitor_check_env(monkeypatch, tmp_path, minimal_config_dict, include_watch=False)
    uri = uri_factory(watch_dir)
    target = URI.from_path(uri) if not isinstance(uri, URI) else uri

    result = run_cmd(cmd_check, uri=target)

    assert result.success is False
    assert result.output["is_monitored"] is False
    assert result.output["priority"] is None
    assert result.output["reason"] is not None


def test_cmd_check_glob_exclusion(monkeypatch, tmp_path, minimal_config_dict):
    """Requirements:
    - MON-001
    - MON-004"""
    watch_dir = setup_monitor_check_env(
        monkeypatch,
        tmp_path,
        minimal_config_dict,
        exclude_globs=["*.tmp"],
    )
    target = watch_dir / "test.tmp"
    target.write_text("temp", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    assert result.output["is_monitored"] is False
    assert "✗" in [decision["symbol"] for decision in result.output["decisions"]]


def test_cmd_check_decision_symbols(monkeypatch, tmp_path, minimal_config_dict):
    """Requirements:
    - MON-001
    - MON-004"""
    watch_dir = setup_monitor_check_env(
        monkeypatch,
        tmp_path,
        minimal_config_dict,
        include_dirnames=["special"],
        include_globs=["*.special"],
    )
    special_dir = watch_dir / "special"
    special_dir.mkdir()
    target = special_dir / "test.special"
    target.write_text("test", encoding="utf-8")

    result = run_cmd(cmd_check, uri=URI.from_path(target))

    assert {"✓", "•"} & {decision["symbol"] for decision in result.output["decisions"]}
