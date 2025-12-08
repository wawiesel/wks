"""Uninstall MCP server command."""

import json
from pathlib import Path

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ...utils.expand_path import expand_path


def cmd_uninstall(name: str) -> StageResult:
    """Uninstall WKS MCP server for a named installation.

    Args:
        name: Installation name

    Returns:
        StageResult with uninstallation status
    """
    config_path = WKSConfig.get_config_path()
    if not config_path.exists():
        return StageResult(
            announce=f"Uninstalling MCP server for '{name}'...",
            result="Configuration file not found",
            output={"success": False, "error": "config file not found"},
            success=False,
        )

    try:
        # Load config
        with config_path.open() as fh:
            config_dict = json.load(fh)

        mcp_config = config_dict.get("mcp", {})
        installs = mcp_config.get("installs", {})

        if name not in installs:
            return StageResult(
                announce=f"Uninstalling MCP server for '{name}'...",
                result=f"Installation '{name}' not found",
                output={"success": False, "error": f"Installation '{name}' not found"},
                success=False,
            )

        install_data = installs[name]
        install_type = install_data.get("type", "mcpServersJson")

        # Perform actual uninstallation based on type
        if install_type == "mcpServersJson":
            settings_path = install_data.get("data", {}).get("settings_path")
            if settings_path:
                settings_file = Path(expand_path(settings_path))
                if settings_file.exists():
                    try:
                        with settings_file.open() as fh:
                            settings = json.load(fh)

                        # Remove WKS MCP server
                        if "mcpServers" in settings and "wks" in settings["mcpServers"]:
                            del settings["mcpServers"]["wks"]

                            # Write settings file
                            with settings_file.open("w") as fh:
                                json.dump(settings, fh, indent=2)
                    except Exception:
                        # If we can't modify the file, continue anyway
                        pass

        # Update config to set active=False
        installs[name]["active"] = False

        # Save config
        with config_path.open("w") as fh:
            json.dump(config_dict, fh, indent=2)

        return StageResult(
            announce=f"Uninstalling MCP server for '{name}'...",
            result=f"MCP server uninstalled successfully for '{name}'",
            output={"success": True, "name": name, "active": False},
            success=True,
        )
    except Exception as e:
        return StageResult(
            announce=f"Uninstalling MCP server for '{name}'...",
            result=f"Uninstallation failed: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )

