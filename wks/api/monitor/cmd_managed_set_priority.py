"""Monitor managed-set-priority API function.

This function updates the priority of a managed directory.
Matches CLI: wksc monitor managed-set-priority <path> <priority>, MCP: wksm_monitor_managed_set_priority
"""

import typer

from ...utils import canonicalize_path, find_matching_path_key
from ..base import StageResult


def cmd_managed_set_priority(
    path: str = typer.Argument(..., help="Path to set priority for"),
    priority: int = typer.Argument(..., help="New priority of the path"),
) -> StageResult:
    """Update priority for a managed directory.

    Args:
        path: Directory path
        priority: New priority score

    Returns:
        StageResult with all 4 stages of data
    """
    from ...config import WKSConfig

    config = WKSConfig.load()

    # Resolve path
    path_resolved = canonicalize_path(path)
    existing_key = find_matching_path_key(config.monitor.managed_directories, path_resolved)

    # If not present, create with given priority
    if existing_key is None:
        config.monitor.managed_directories[path_resolved] = priority
        result = {
            "success": True,
            "message": f"Set priority for {path_resolved}: {priority} (created)",
            "path_stored": path_resolved,
            "new_priority": priority,
            "created": True,
        }
    else:
        # Update existing priority
        old_priority = config.monitor.managed_directories[existing_key]
        config.monitor.managed_directories[existing_key] = priority
        result = {
            "success": True,
            "message": f"Updated priority for {existing_key}: {old_priority} → {priority}",
            "old_priority": old_priority,
            "new_priority": priority,
            "path_stored": existing_key,
            "created": False,
        }

    config.save()

    return StageResult(
        announce=f"Setting priority for managed directory: {path} to {priority}",
        result=str(result.get("message", "")),
        output=result,
    )
