"""Install MCP server command."""

import json
import sys
from pathlib import Path

from ..base import StageResult
from ..config.get_config_path import get_config_path
from ...utils.expand_path import expand_path


def cmd_install(name: str, install_type: str = "mcpServersJson", settings_path: str | None = None) -> StageResult:
    """Install WKS MCP server for a named installation.

    Args:
        name: Installation name
        install_type: Installation type (default: "mcpServersJson")
        settings_path: Path to settings file (required for mcpServersJson type)

    Returns:
        StageResult with installation status
    """
    if install_type == "mcpServersJson" and not settings_path:
        return StageResult(
            announce=f"Installing MCP server for '{name}'...",
            result="Error: settings_path is required for mcpServersJson type",
            output={"success": False, "error": "settings_path required"},
            success=False,
        )

    config_path = get_config_path()
    if not config_path.exists():
        return StageResult(
            announce=f"Installing MCP server for '{name}'...",
            result="Configuration file not found",
            output={"success": False, "error": "config file not found"},
            success=False,
        )

    try:
        # Load config
        with config_path.open() as fh:
            config_dict = json.load(fh)

        # Ensure mcp section exists
        if "mcp" not in config_dict:
            config_dict["mcp"] = {}
        if "installs" not in config_dict["mcp"]:
            config_dict["mcp"]["installs"] = {}

        # Update or create installation entry
        if name not in config_dict["mcp"]["installs"]:
            config_dict["mcp"]["installs"][name] = {
                "type": install_type,
                "active": True,
                "data": {"settings_path": settings_path} if settings_path else {},
            }
        else:
            config_dict["mcp"]["installs"][name]["active"] = True
            if settings_path:
                config_dict["mcp"]["installs"][name]["data"]["settings_path"] = settings_path

        # Perform actual installation based on type
        if install_type == "mcpServersJson":
            settings_file = Path(expand_path(settings_path))
            settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Load or create settings file
            if settings_file.exists():
                try:
                    with settings_file.open() as fh:
                        settings = json.load(fh)
                except Exception:
                    settings = {}
            else:
                settings = {}

            # Ensure mcpServers section exists
            if "mcpServers" not in settings:
                settings["mcpServers"] = {}

            # Add WKS MCP server
            wks_command = [str(Path(sys.executable).parent / "wksm"), "run"]
            settings["mcpServers"]["wks"] = {
                "command": "wksm",
                "args": ["run"],
            }

            # Write settings file
            with settings_file.open("w") as fh:
                json.dump(settings, fh, indent=2)

        # Save config
        with config_path.open("w") as fh:
            json.dump(config_dict, fh, indent=2)

        return StageResult(
            announce=f"Installing MCP server for '{name}'...",
            result=f"MCP server installed successfully for '{name}'",
            output={"success": True, "name": name, "type": install_type, "active": True},
            success=True,
        )
    except Exception as e:
        return StageResult(
            announce=f"Installing MCP server for '{name}'...",
            result=f"Installation failed: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )

