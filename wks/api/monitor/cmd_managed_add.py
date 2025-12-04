"""Monitor managed-add API function.

This function adds a managed directory with priority.
Matches CLI: wksc monitor managed-add <path> <priority>, MCP: wksm_monitor_managed_add
"""

import typer

from ...utils import canonicalize_path, find_matching_path_key
from ..base import StageResult


def cmd_managed_add(
    path: str = typer.Argument(..., help="Path to manage"),
    priority: int = typer.Argument(..., help="Priority of the path"),
) -> StageResult:
    """Add a managed directory with priority.

    Args:
        path: Directory path to add
        priority: Priority score

    Returns:
        StageResult with all 4 stages of data
    """
    from ...config import WKSConfig

    config = WKSConfig.load()

    # Resolve path
    path_resolved = canonicalize_path(path)

    # Check if already exists
    existing_key = find_matching_path_key(config.monitor.managed_directories, path_resolved)
    if existing_key is not None:
        result = {
            "success": False,
            "message": f"Already a managed directory: {existing_key}",
            "already_exists": True,
        }
        return StageResult(
            announce=f"Adding managed directory: {path}",
            result=str(result.get("message", "")),
            output=result,
        )

    # Add to managed directories
    config.monitor.managed_directories[path_resolved] = priority

    result = {
        "success": True,
        "message": f"Added managed directory: {path_resolved} (priority {priority})",
        "path_stored": path_resolved,
        "priority": priority,
    }

    if result.get("success"):
        config.save()

    return StageResult(
        announce=f"Adding managed directory: {path}",
        result=str(result.get("message", "")),
        output=result,
    )
