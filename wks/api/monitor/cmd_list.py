"""Monitor list API function.

This function gets the contents of a monitor configuration list.
Matches CLI: wksc monitor <list-name> list, MCP: wksm_monitor_list
"""

import typer

from ..base import StageResult
from ...config import WKSConfig
from ...monitor import MonitorController


def cmd_list(
    list_name: str = typer.Argument(..., help="Name of list (include_paths, exclude_paths, etc.)"),
) -> StageResult:
    """Get contents of a monitor configuration list.

    Args:
        list_name: Name of list to retrieve

    Returns:
        StageResult with list contents and validation info
    """
    from ...config import WKSConfig

    config = WKSConfig.load()
    result = MonitorController.get_list(config.monitor, list_name)

    return StageResult(
        announce=f"Retrieving {list_name}...",
        result=f"Retrieved {list_name} ({result.get('count', 0)} items)",
        output=result,
    )

