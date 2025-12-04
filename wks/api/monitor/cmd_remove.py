"""Monitor remove API function.

This function removes a value from a monitor configuration list.
Matches CLI: wksc monitor <list-name> remove <value>, MCP: wksm_monitor_remove
"""

import typer

from ...config import WKSConfig
from ...monitor import MonitorOperations
from ..base import StageResult


def cmd_remove(
    list_name: str = typer.Argument(..., help="Name of list to modify"),
    value: str = typer.Argument(..., help="Value to remove"),
) -> StageResult:
    """Remove a value from a monitor configuration list.

    Args:
        list_name: Name of list to modify
        value: Value to remove

    Returns:
        StageResult with success status and message
    """

    config = WKSConfig.load()

    # Determine if this list uses path resolution
    resolve_path = list_name in ("include_paths", "exclude_paths")

    result_obj = MonitorOperations.remove_from_list(config.monitor, list_name, value, resolve_path=resolve_path)
    result = result_obj.model_dump()

    if result.get("success"):
        config.save()

    return StageResult(
        announce=f"Removing from {list_name}: {value}",
        result=str(result.get("message", "")),
        output=result,
    )
