"""Unit tests for monitor cmd_status (no mocks, real mongomock via config)."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.monitor.cmd_status import cmd_status

pytestmark = pytest.mark.monitor


def test_cmd_status_success(monkeypatch, tmp_path, minimal_config_dict):
    """Status succeeds with default config and no issues."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    cfg = minimal_config_dict
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["tracked_files"] == 0
    assert result.output["issues"] == []


def test_cmd_status_sets_success_based_on_issues(monkeypatch, tmp_path, minimal_config_dict):
    """Invalid priority dirs should surface issues and fail success flag."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    cfg = minimal_config_dict
    cfg["monitor"]["priority"]["dirs"] = {"/invalid/path": 100.0}
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_status)

    assert result.success is False
    assert any("Priority directory invalid" in issue for issue in result.output["issues"])
