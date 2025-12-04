"""Monitor add API function.

This function adds a value to a monitor configuration list.
Matches CLI: wksc monitor <list-name> add <value>, MCP: wksm_monitor_add
"""

import typer

from ...config import WKSConfig
from ...monitor import MonitorOperations
from ..base import StageResult


def cmd_add(
    list_name: str = typer.Argument(..., help="Name of list to modify"),
    value: str = typer.Argument(..., help="Value to add"),
) -> StageResult:
    """Add a value to a monitor configuration list.

    Args:
        list_name: Name of list to modify
        value: Value to add

    Returns:
        StageResult with success status and message
    """

    config = WKSConfig.load()

    # Determine if this list uses path resolution
    resolve_path = list_name in ("include_paths", "exclude_paths")

    result_obj = MonitorOperations.add_to_list(config.monitor, list_name, value, resolve_path=resolve_path)
    result = result_obj.model_dump()

    if result.get("success"):
        config.save()

    return StageResult(
        announce=f"Adding to {list_name}: {value}",
        result=str(result.get("message", "")),
        output=result,
    )
