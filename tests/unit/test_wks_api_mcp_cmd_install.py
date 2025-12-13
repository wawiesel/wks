"""Unit tests for wks.api.mcp.cmd_install module."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.mcp import cmd_install

pytestmark = pytest.mark.mcp


def test_cmd_install_missing_settings_path():
    """Test cmd_install fails when settings_path is missing for mcpServersJson."""
    result = run_cmd(cmd_install.cmd_install, name="test", install_type="mcpServersJson", settings_path=None)

    assert result.success is False
    assert "settings_path is required" in result.result
    assert result.output["success"] is False
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_install_config_not_found(tmp_path, monkeypatch):
    """Test cmd_install when config file doesn't exist."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # Don't create config.json
    result = run_cmd(cmd_install.cmd_install, name="test", install_type="mcpServersJson", settings_path="~/test.json")

    assert result.success is False
    assert "Configuration file not found" in result.result
    assert result.output["success"] is False
    assert "errors" in result.output
    assert "warnings" in result.output


def test_cmd_install_success_new_installation(wks_home, minimal_config_dict):
    """Test cmd_install successfully creates new installation."""
    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    settings_path = wks_home / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    result = run_cmd(
        cmd_install.cmd_install, name="test", install_type="mcpServersJson", settings_path=str(settings_path)
    )

    assert result.success is True
    assert "installed successfully" in result.result
    assert result.output["success"] is True
    assert result.output["name"] == "test"
    assert result.output["active"] is True
    assert "errors" in result.output
    assert "warnings" in result.output

    # Verify config was updated
    with config_path.open() as fh:
        updated_config = json.load(fh)
    assert "mcp" in updated_config
    assert "test" in updated_config["mcp"]["installs"]
    assert updated_config["mcp"]["installs"]["test"]["active"] is True

    # Verify settings file was created with WKS MCP server
    assert settings_path.exists()
    with settings_path.open() as fh:
        settings = json.load(fh)
    assert "mcpServers" in settings
    assert "wks" in settings["mcpServers"]


def test_cmd_install_success_existing_installation(wks_home, minimal_config_dict, tmp_path):
    """Test cmd_install successfully updates existing installation."""
    # Add existing mcp installation to standard config
    minimal_config_dict["mcp"] = {
        "installs": {
            "test": {
                "type": "mcpServersJson",
                "active": False,
                "data": {"settings_path": "~/old.json"},
            }
        }
    }

    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))

    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    result = run_cmd(
        cmd_install.cmd_install, name="test", install_type="mcpServersJson", settings_path=str(settings_path)
    )

    assert result.success is True
    assert "errors" in result.output
    assert "warnings" in result.output
    # Verify config was updated
    with config_path.open() as fh:
        updated_config = json.load(fh)
    assert updated_config["mcp"]["installs"]["test"]["active"] is True


def test_cmd_install_exception_handling(wks_home, minimal_config_dict, monkeypatch):
    """Test cmd_install handles exceptions during installation."""
    config_path = wks_home / "config.json"
    config_path.write_text(json.dumps(minimal_config_dict))
    # Make json.dump raise an exception when saving config
    original_dump = json.dump

    def mock_dump(*args, **kwargs):
        # Only fail on the config save (second dump call)
        if "mcp" in str(args[0]) or "installs" in str(args[0]):
            raise OSError("Permission denied")
        return original_dump(*args, **kwargs)

    monkeypatch.setattr("json.dump", mock_dump)

    result = run_cmd(cmd_install.cmd_install, name="test", install_type="mcpServersJson", settings_path="~/test.json")

    assert result.success is False
    assert "Installation failed" in result.result
    assert "errors" in result.output
    assert "warnings" in result.output
