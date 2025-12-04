"""Monitor check API function.

This function checks if a path would be monitored and calculates its priority.
Matches CLI: wksc monitor check <path>, MCP: wksm_monitor_check
"""

import typer

from ..base import StageResult
from ...config import WKSConfig
from ...monitor import MonitorController


def cmd_check(
    path: str = typer.Argument(..., help="File or directory path to check"),
) -> StageResult:
    """Check if a path would be monitored and calculate its priority.

    Args:
        path: File or directory path to check

    Returns:
        StageResult with is_monitored, priority, and path information
    """
    config = WKSConfig.load()
    result = MonitorController.check_path(config.monitor, path)

    if result.get("is_monitored"):
        res_msg = f"Path is monitored with priority {result.get('priority', 0)}"
    else:
        res_msg = "Path is not monitored"

    return StageResult(
        announce=f"Checking if path would be monitored: {path}",
        result=res_msg,
        output=result,
    )
