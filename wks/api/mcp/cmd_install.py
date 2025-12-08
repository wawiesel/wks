"""Install MCP server command."""

import json
import sys
from collections.abc import Iterator
from pathlib import Path

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
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
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        if install_type == "mcpServersJson" and not settings_path:
            yield (1.0, "Complete")
            result_obj.result = "Error: settings_path is required for mcpServersJson type"
            result_obj.output = {
                "success": False,
                "error": "settings_path required",
                "errors": ["settings_path is required for mcpServersJson type"],
                "warnings": [],
            }
            result_obj.success = False
            return

        yield (0.1, "Checking configuration...")
        config_path = WKSConfig.get_config_path()
        if not config_path.exists():
            yield (1.0, "Complete")
            result_obj.result = "Configuration file not found"
            result_obj.output = {
                "success": False,
                "error": "config file not found",
                "errors": ["Configuration file not found"],
                "warnings": [],
            }
            result_obj.success = False
            return

        try:
            yield (0.2, "Loading configuration...")
            with config_path.open() as fh:
                config_dict = json.load(fh)

            yield (0.3, "Updating MCP configuration...")
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

            yield (0.5, "Performing installation...")
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
                settings["mcpServers"]["wks"] = {
                    "command": "wksm",
                    "args": ["run"],
                }

                # Write settings file
                with settings_file.open("w") as fh:
                    json.dump(settings, fh, indent=2)

            yield (0.8, "Saving configuration...")
            # Save config
            with config_path.open("w") as fh:
                json.dump(config_dict, fh, indent=2)

            yield (1.0, "Complete")
            result_obj.result = f"MCP server installed successfully for '{name}'"
            result_obj.output = {
                "success": True,
                "name": name,
                "type": install_type,
                "active": True,
                "errors": [],
                "warnings": [],
            }
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Installation failed: {e}"
            result_obj.output = {
                "success": False,
                "error": str(e),
                "errors": [str(e)],
                "warnings": [],
            }
            result_obj.success = False

    return StageResult(
        announce=f"Installing MCP server for '{name}'...",
        progress_callback=do_work,
    )
