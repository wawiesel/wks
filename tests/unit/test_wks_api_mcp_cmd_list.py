"""Unit tests for wks.api.mcp.cmd_list module."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp.cmd_list import cmd_list

pytestmark = pytest.mark.mcp


def test_cmd_list_no_mcp_config(wks_home, minimal_config_dict):
    """Test cmd_list when no MCP config exists."""
    # Use standard config (no mcp section)
    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    result = run_cmd(cmd_list)

    assert result.success is True
    assert result.output["count"] == 0
    assert result.output["installations"] == []
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_list_with_installations(wks_home, minimal_config_dict):
    """Test cmd_list with MCP installations."""
    # Add mcp section to standard config
    minimal_config_dict["mcp"] = {
        "installs": {
            "gemini": {
                "type": "mcpServersJson",
                "active": True,
                "data": {"settings_path": "~/Library/Application Support/Google/ai-studio/settings.json"},
            }
        }
    }

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    result = run_cmd(cmd_list)

    assert result.success is True
    assert result.output["count"] == 1
    assert len(result.output["installations"]) == 1
    assert result.output["installations"][0]["name"] == "gemini"
    assert result.output["installations"][0]["active"] is True
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_list_config_not_found(tmp_path, monkeypatch):
    """Test cmd_list when config file doesn't exist."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # Don't create config.json
    result = run_cmd(cmd_list)

    assert result.success is False
    assert "Configuration file not found" in result.result
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_list_invalid_json(wks_home):
    """Test cmd_list when config file has invalid JSON."""
    config_path = wks_home / "config.json"
    config_path.write_text("invalid json {")

    result = run_cmd(cmd_list)

    assert result.success is False
    assert "Configuration error" in result.result  # Changed from WKSConfig.load()
    assert "errors" in result.output
    assert "warnings" in result.output
