"""Unit tests for wks.api.mcp.cmd_uninstall module."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp import cmd_uninstall

pytestmark = pytest.mark.mcp


def test_cmd_uninstall_config_not_found(tmp_path, monkeypatch):
    """Test cmd_uninstall when config file doesn't exist."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # Don't create config.json
    result = run_cmd(cmd_uninstall.cmd_uninstall, name="test")

    assert result.success is False
    assert "Configuration file not found" in result.result
    assert result.output["success"] is False
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_uninstall_not_found(wks_home, minimal_config_dict):
    """Test cmd_uninstall when installation doesn't exist."""
    # Add empty mcp section to standard config
    minimal_config_dict["mcp"] = {"installs": {}}

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    result = run_cmd(cmd_uninstall.cmd_uninstall, name="nonexistent")

    assert result.success is False
    assert "not found" in result.result
    assert result.output["success"] is False
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_uninstall_success(wks_home, minimal_config_dict):
    """Test cmd_uninstall successfully uninstalls."""
    settings_path = wks_home / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Create settings file with WKS MCP server
    settings = {
        "mcpServers": {
            "wks": {"command": "wksm", "args": ["run"]},
            "other": {"command": "other", "args": []},
        }
    }
    settings_path.write_text(json.dumps(settings))

    # Add mcp installation to standard config
    minimal_config_dict["mcp"] = {
        "installs": {
            "test": {
                "type": "mcpServersJson",
                "active": True,
                "data": {"settings_path": str(settings_path)},
            }
        }
    }

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    result = run_cmd(cmd_uninstall.cmd_uninstall, name="test")

    assert result.success is True
    assert "uninstalled successfully" in result.result
    assert result.output["success"] is True
    assert result.output["name"] == "test"
    assert result.output["active"] is False
    assert "errors" in result.output
    assert "warnings" in result.output

    # Verify config was updated
    with config_path.open() as fh:
        updated_config = json.load(fh)
    assert updated_config["mcp"]["installs"]["test"]["active"] is False

    # Verify WKS was removed from settings file
    with settings_path.open() as fh:
        updated_settings = json.load(fh)
    assert "wks" not in updated_settings["mcpServers"]
    assert "other" in updated_settings["mcpServers"]


def test_cmd_uninstall_settings_file_not_exists(wks_home, minimal_config_dict):
    """Test cmd_uninstall when settings file doesn't exist."""
    settings_path = wks_home / "nonexistent.json"

    # Add mcp installation pointing to non-existent settings file
    minimal_config_dict["mcp"] = {
        "installs": {
            "test": {
                "type": "mcpServersJson",
                "active": True,
                "data": {"settings_path": str(settings_path)},
            }
        }
    }

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    result = run_cmd(cmd_uninstall.cmd_uninstall, name="test")

    # Should still succeed even if settings file doesn't exist
    assert result.success is True
    assert result.output["active"] is False
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_uninstall_exception_handling(wks_home, minimal_config_dict, monkeypatch):
    """Test cmd_uninstall handles exceptions during uninstallation."""
    # Add mcp installation to standard config
    minimal_config_dict["mcp"] = {
        "installs": {
            "test": {
                "type": "mcpServersJson",
                "active": True,
                "data": {"settings_path": "~/test.json"},
            }
        }
    }

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))
    # Make json.dump raise an exception when saving config
    original_dump = json.dump

    def mock_dump(*args, **kwargs):
        # Only fail on the config save
        if "mcp" in str(args[0]) or "installs" in str(args[0]):
            raise OSError("Permission denied")
        return original_dump(*args, **kwargs)

    monkeypatch.setattr("json.dump", mock_dump)

    result = run_cmd(cmd_uninstall.cmd_uninstall, name="test")

    assert result.success is False
    assert "Uninstallation failed" in result.result
    assert "errors" in result.output
    assert "warnings" in result.output
