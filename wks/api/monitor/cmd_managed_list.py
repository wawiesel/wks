"""Monitor managed-list API function.

This function lists all managed directories.
Matches CLI: wksc monitor managed-list, MCP: wksm_monitor_managed_list
"""

from ...monitor import MonitorController
from ..base import StageResult


def cmd_managed_list() -> StageResult:
    """List all managed directories with their priorities.

    Returns:
        StageResult with all 4 stages of data
    """
    from ...config import WKSConfig

    config = WKSConfig.load()
    result_obj = MonitorController.get_managed_directories(config.monitor)
    result = result_obj.model_dump()

    return StageResult(
        announce="Listing managed directories...",
        result="Managed directories retrieved",
        output=result,
    )
