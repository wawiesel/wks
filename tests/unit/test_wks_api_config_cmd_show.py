"""Unit tests for config cmd_show."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.cmd_show import cmd_show

pytestmark = pytest.mark.config


def build_config(tmp_path, monkeypatch):
    """Create a valid config file."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    config = {
        "monitor": {"filter": {}, "priority": {"dirs": {"~": 100.0}, "weights": {}}, "database": "monitor", "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0}},
        "database": {"type": "mongomock", "prefix": "wks", "data": {}},
        "daemon": {"type": "macos", "data": {"label": "com.test.wks", "log_file": "daemon.log", "error_log_file": "daemon.error.log", "keep_alive": True, "run_at_load": False}},
    }
    (tmp_path / "config.json").write_text(json.dumps(config))


class TestCmdShow:
    def test_cmd_show_no_section(self, tmp_path, monkeypatch):
        build_config(tmp_path, monkeypatch)
        result = run_cmd(cmd_show, "")
        assert result.success
        assert "sections" in result.output["content"]
        assert len(result.output["content"]["sections"]) > 0

    def test_cmd_show_with_valid_section(self, tmp_path, monkeypatch):
        build_config(tmp_path, monkeypatch)
        result = run_cmd(cmd_show, "monitor")
        assert result.success
        assert result.output["section"] == "monitor"
        assert isinstance(result.output["content"], dict)

    def test_cmd_show_with_invalid_section(self, tmp_path, monkeypatch):
        build_config(tmp_path, monkeypatch)
        result = run_cmd(cmd_show, "invalid_section")
        assert not result.success
        assert result.output["errors"]
