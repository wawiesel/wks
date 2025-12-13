"""List MCP installations command."""

import json
from collections.abc import Iterator

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import McpListOutput


def cmd_list() -> StageResult:
    """List MCP installations.

    Returns:
        StageResult with list of installations and their status
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        yield (0.2, "Loading configuration...")
        config_path = WKSConfig.get_config_path()

        if not config_path.exists():
            yield (1.0, "Complete")
            result_obj.result = "Configuration file not found"
            result_obj.output = McpListOutput(
                installations=[],
                count=0,
                errors=["Configuration file not found"],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.5, "Reading configuration...")
        try:
            with config_path.open() as fh:
                config_dict = json.load(fh)
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Error reading config: {e}"
            result_obj.output = McpListOutput(
                installations=[],
                count=0,
                errors=[str(e)],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.7, "Processing MCP installations...")
        mcp_config = config_dict.get("mcp", {})
        installs = mcp_config.get("installs", {})

        installations = []
        for name, install_data in installs.items():
            installations.append(
                {
                    "name": name,
                    "type": install_data.get("type", "unknown"),
                    "active": install_data.get("active", False),
                    "path": install_data.get("data", {}).get("settings_path", "unknown"),
                }
            )

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(installations)} installation(s)"
        result_obj.output = McpListOutput(
            installations=installations,
            count=len(installations),
            errors=[],
            warnings=[],
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing MCP installations...",
        progress_callback=do_work,
    )
