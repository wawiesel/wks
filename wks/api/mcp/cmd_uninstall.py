"""Uninstall MCP server command."""

import json
from collections.abc import Iterator

from wks.api.config.normalize_path import normalize_path

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
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
        try:
            yield (0.2, "Loading configuration...")
            config = WKSConfig.load()

            yield (0.3, "Checking installation...")
            if name not in config.mcp.installs:
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

            install = config.mcp.installs[name]

            yield (0.5, "Performing uninstallation...")
            # Perform actual uninstallation based on type
            if install.type == "mcpServersJson":
                settings_path = install.data.settings_path
                settings_file = normalize_path(settings_path)
                if settings_file.exists():
                    try:
                        with settings_file.open("r") as fh:
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
            install.active = False

            yield (0.9, "Saving configuration...")
            # Save config
            config.save()

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
