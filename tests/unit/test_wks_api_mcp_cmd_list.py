"""Unit tests for wks.api.mcp.cmd_list module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.mcp.cmd_list import cmd_list

pytestmark = pytest.mark.mcp


def test_cmd_list_no_mcp_config(tmp_path, monkeypatch):
    """Test cmd_list when no MCP config exists."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)

    config_path = tmp_path / "config.json"
    config_dict = {
        "monitor": {"filter": {}, "priority": {}, "database": "monitor", "sync": {}},
        "database": {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}},
        "daemon": {"type": "macos", "data": {"label": "com.test.wks", "log_file": "daemon.log", "error_log_file": "daemon.error.log", "keep_alive": True, "run_at_load": False}},
    }
    config_path.write_text(json.dumps(config_dict))

    monkeypatch.setattr(WKSConfig, "get_config_path", lambda: config_path)
    result = run_cmd(cmd_list)

    assert result.success is True
    assert result.output["count"] == 0
    assert result.output["installations"] == []
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_list_with_installations(tmp_path, monkeypatch):
    """Test cmd_list with MCP installations."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    monkeypatch.delenv("HOME", raising=False)

    config_path = tmp_path / "config.json"
    config_dict = {
        "monitor": {"filter": {}, "priority": {}, "database": "monitor", "sync": {}},
        "database": {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}},
        "daemon": {"type": "macos", "data": {"label": "com.test.wks", "log_file": "daemon.log", "error_log_file": "daemon.error.log", "keep_alive": True, "run_at_load": False}},
        "mcp": {
            "installs": {
                "gemini": {
                    "type": "mcpServersJson",
                    "active": True,
                    "data": {"settings_path": "~/Library/Application Support/Google/ai-studio/settings.json"},
                }
            }
        },
    }
    config_path.write_text(json.dumps(config_dict))

    monkeypatch.setattr(WKSConfig, "get_config_path", lambda: config_path)
    result = run_cmd(cmd_list)

    assert result.success is True
    assert result.output["count"] == 1
    assert len(result.output["installations"]) == 1
    assert result.output["installations"][0]["name"] == "gemini"
    assert result.output["installations"][0]["active"] is True
    assert "errors" in result.output
    assert "warnings" in result.output

