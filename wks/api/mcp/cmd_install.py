"""Install MCP server command."""

import json
from collections.abc import Iterator

from wks.api.config.normalize_path import normalize_path

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import McpInstallOutput


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
        from .McpServersJsonData import McpServersJsonData
        from .McpServersJsonInstall import McpServersJsonInstall

        if install_type == "mcpServersJson" and not settings_path:
            yield (1.0, "Complete")
            result_obj.result = "Error: settings_path is required for mcpServersJson type"
            result_obj.output = McpInstallOutput(
                success=False,
                name=name,
                type=install_type,
                active=False,
                errors=["settings_path is required for mcpServersJson type"],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        try:
            yield (0.2, "Loading configuration...")
            config = WKSConfig.load()

            yield (0.3, "Updating MCP configuration...")
            # Update or create installation entry
            if name not in config.mcp.installs:
                if install_type == "mcpServersJson":
                    assert settings_path is not None
                    config.mcp.installs[name] = McpServersJsonInstall(
                        type="mcpServersJson",
                        active=True,
                        data=McpServersJsonData(settings_path=settings_path),
                    )
            else:
                install = config.mcp.installs[name]
                install.active = True
                if install.type == "mcpServersJson" and settings_path:
                    install.data.settings_path = settings_path

            yield (0.5, "Performing installation...")
            # Perform actual installation based on type
            if install_type == "mcpServersJson":
                assert settings_path is not None  # Checked at line 27
                settings_file = normalize_path(settings_path)
                settings_file.parent.mkdir(parents=True, exist_ok=True)

                # Load or create settings file
                if settings_file.exists():
                    try:
                        with settings_file.open("r") as fh:
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
            config.save()

            yield (1.0, "Complete")
            result_obj.result = f"MCP server installed successfully for '{name}'"
            result_obj.output = McpInstallOutput(
                success=True,
                name=name,
                type=install_type,
                active=True,
                errors=[],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Installation failed: {e}"
            result_obj.output = McpInstallOutput(
                success=False,
                name=name,
                type=install_type,
                active=False,
                errors=[str(e)],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce=f"Installing MCP server for '{name}'...",
        progress_callback=do_work,
    )
