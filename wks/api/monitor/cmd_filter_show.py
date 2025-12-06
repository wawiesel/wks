"""Monitor filter-show API function.

This function gets the contents of a monitor configuration list or, if no list
is specified, returns the available list names.
Matches CLI: wksc monitor filter show [<list-name>], MCP: wksm_monitor_filter_show
"""

from ...api.config.WKSConfig import WKSConfig
from ..base import StageResult
from .MonitorConfig import MonitorConfig


def cmd_filter_show(list_name: str | None = None) -> StageResult:
    """Get contents of a monitor configuration list or list available names."""

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    if not isinstance(list_name, str) or not list_name:
        available_lists = list(MonitorConfig.get_filter_list_names())
        result = {"available_lists": available_lists, "success": True}
        return StageResult(
            announce="Listing available monitor lists...",
            result="Available monitor lists",
            output=result,
        )

    if list_name not in MonitorConfig.get_filter_list_names():
        raise ValueError(f"Unknown list_name: {list_name!r}")

    items = list(getattr(monitor_cfg.filter, list_name))
    result = {"list_name": list_name, "items": items, "count": len(items), "success": True}

    return StageResult(
        announce=f"Showing {list_name}...",
        result=f"Showing {list_name} ({len(items)} items)",
        output=result,
    )
