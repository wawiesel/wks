"""Uninstall MCP server command."""

import json
from collections.abc import Iterator
from pathlib import Path

from ...utils.expand_path import expand_path
from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import McpUninstallOutput


def cmd_uninstall(name: str) -> StageResult:
    """Uninstall WKS MCP server for a named installation.

    Args:
        name: Installation name

    Returns:
        StageResult with uninstallation status
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        yield (0.1, "Checking configuration...")
        config_path = WKSConfig.get_config_path()
        if not config_path.exists():
            yield (1.0, "Complete")
            result_obj.result = "Configuration file not found"
            result_obj.output = McpUninstallOutput(
                success=False,
                name=name,
                active=False,
                errors=["Configuration file not found"],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        try:
            yield (0.2, "Loading configuration...")
            with config_path.open() as fh:
                config_dict = json.load(fh)

            yield (0.3, "Checking installation...")
            mcp_config = config_dict.get("mcp", {})
            installs = mcp_config.get("installs", {})

            if name not in installs:
                yield (1.0, "Complete")
                result_obj.result = f"Installation '{name}' not found"
                result_obj.output = McpUninstallOutput(
                    success=False,
                    name=name,
                    active=False,
                    errors=[f"Installation '{name}' not found"],
                    warnings=[],
                ).model_dump(mode="python")
                result_obj.success = False
                return

            install_data = installs[name]
            install_type = install_data.get("type", "mcpServersJson")

            yield (0.5, "Performing uninstallation...")
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

            yield (0.8, "Updating configuration...")
            # Update config to set active=False
            installs[name]["active"] = False

            yield (0.9, "Saving configuration...")
            # Save config
            with config_path.open("w") as fh:
                json.dump(config_dict, fh, indent=2)

            yield (1.0, "Complete")
            result_obj.result = f"MCP server uninstalled successfully for '{name}'"
            result_obj.output = McpUninstallOutput(
                success=True,
                name=name,
                active=False,
                errors=[],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Uninstallation failed: {e}"
            result_obj.output = McpUninstallOutput(
                success=False,
                name=name,
                active=False,
                errors=[str(e)],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce=f"Uninstalling MCP server for '{name}'...",
        progress_callback=do_work,
    )
