"""List MCP installations command."""

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

        try:
            config = WKSConfig.load()
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Configuration error: {e}"
            result_obj.output = McpListOutput(
                installations=[],
                count=0,
                errors=[str(e)],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.7, "Processing MCP installations...")
        installations = []
        for name, install in config.mcp.installs.items():
            installations.append(
                {
                    "name": name,
                    "type": install.type,
                    "active": install.active,
                    "path": install.data.settings_path,
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
