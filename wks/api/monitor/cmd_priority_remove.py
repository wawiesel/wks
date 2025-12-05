"""Monitor priority-remove API function.

This function removes a priority directory.
Matches CLI: wksc monitor priority remove <path>, MCP: wksm_monitor_priority_remove
"""

import typer

from ...utils import canonicalize_path, find_matching_path_key
from ..base import StageResult


def cmd_priority_remove(
    path: str = typer.Argument(..., help="Path to unmanage"),
) -> StageResult:
    """Remove a priority directory.

    Args:
        path: Directory path to remove

    Returns:
        StageResult with all 4 stages of data
    """
    from ...config import WKSConfig

    config = WKSConfig.load()

    if not config.monitor.priority.dirs:
        result = {
            "success": False,
            "message": "No priority directories configured",
            "not_found": True,
        }
        return StageResult(
            announce=f"Removing priority directory: {path}",
            result=str(result.get("message", "")),
            output=result,
        )

    # Resolve path
    path_resolved = canonicalize_path(path)
    existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

    # Check if exists
    if existing_key is None:
        result = {
            "success": False,
            "message": f"Not a priority directory: {path_resolved}",
            "not_found": True,
        }
        return StageResult(
            announce=f"Removing priority directory: {path}",
            result=str(result.get("message", "")),
            output=result,
        )

    # Get priority before removing
    priority = config.monitor.priority.dirs[existing_key]

    # Remove from priority directories
    del config.monitor.priority.dirs[existing_key]

    result = {
        "success": True,
        "message": f"Removed priority directory: {existing_key}",
        "path_removed": existing_key,
        "priority": priority,
    }

    if result.get("success"):
        config.save()

    return StageResult(
        announce=f"Removing priority directory: {path}",
        result=str(result.get("message", "")),
        output=result,
    )
