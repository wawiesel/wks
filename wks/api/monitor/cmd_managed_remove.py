"""Monitor managed-remove API function.

This function removes a managed directory.
Matches CLI: wksc monitor managed-remove <path>, MCP: wksm_monitor_managed_remove
"""

import typer

from ...utils import canonicalize_path, find_matching_path_key
from ..base import StageResult


def cmd_managed_remove(
    path: str = typer.Argument(..., help="Path to unmanage"),
) -> StageResult:
    """Remove a managed directory.

    Args:
        path: Directory path to remove

    Returns:
        StageResult with all 4 stages of data
    """
    from ...config import WKSConfig

    config = WKSConfig.load()

    if not config.monitor.managed_directories:
        result = {
            "success": False,
            "message": "No managed_directories configured",
            "not_found": True,
        }
        return StageResult(
            announce=f"Removing managed directory: {path}",
            result=str(result.get("message", "")),
            output=result,
        )

    # Resolve path
    path_resolved = canonicalize_path(path)
    existing_key = find_matching_path_key(config.monitor.managed_directories, path_resolved)

    # Check if exists
    if existing_key is None:
        result = {
            "success": False,
            "message": f"Not a managed directory: {path_resolved}",
            "not_found": True,
        }
        return StageResult(
            announce=f"Removing managed directory: {path}",
            result=str(result.get("message", "")),
            output=result,
        )

    # Get priority before removing
    priority = config.monitor.managed_directories[existing_key]

    # Remove from managed directories
    del config.monitor.managed_directories[existing_key]

    result = {
        "success": True,
        "message": f"Removed managed directory: {existing_key}",
        "path_removed": existing_key,
        "priority": priority,
    }

    if result.get("success"):
        config.save()

    return StageResult(
        announce=f"Removing managed directory: {path}",
        result=str(result.get("message", "")),
        output=result,
    )
