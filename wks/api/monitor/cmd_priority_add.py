"""Monitor priority-add API function.

This function sets or updates the priority of a priority directory.
Matches CLI: wksc monitor priority add <path> <priority>, MCP: wksm_monitor_priority_add
"""

import typer

from ...utils import canonicalize_path, find_matching_path_key
from ..base import StageResult


def cmd_priority_add(
    path: str = typer.Argument(..., help="Path to set priority for"),
    priority: float = typer.Argument(..., help="New priority of the path"),
) -> StageResult:
    """Set or update priority for a priority directory (creates if missing).

    Args:
        path: Directory path
        priority: New priority score

    Returns:
        StageResult with all 4 stages of data
    """
    from ...api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()

    # Resolve path
    path_resolved = canonicalize_path(path)
    existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

    # If not present, create with given priority
    if existing_key is None:
        config.monitor.priority.dirs[path_resolved] = priority
        result = {
            "success": True,
            "message": f"Set priority for {path_resolved}: {priority} (created)",
            "path_stored": path_resolved,
            "new_priority": priority,
            "created": True,
            "already_exists": False,
        }
    else:
        # Update existing priority
        old_priority = config.monitor.priority.dirs[existing_key]
        config.monitor.priority.dirs[existing_key] = priority
        result = {
            "success": True,
            "message": f"Updated priority for {existing_key}: {old_priority} → {priority}",
            "old_priority": old_priority,
            "new_priority": priority,
            "path_stored": existing_key,
            "created": False,
            "already_exists": True,
        }

    config.save()

    return StageResult(
        announce=f"Setting priority for priority directory: {path} to {priority}",
        result=str(result.get("message", "")),
        output=result,
    )
