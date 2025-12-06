"""Monitor filter-show API function.

This function gets the contents of a monitor configuration list or, if no list
is specified, returns the available list names.
Matches CLI: wksc monitor filter show [<list-name>], MCP: wksm_monitor_filter_show
"""

import typer

from ...api.config.WKSConfig import WKSConfig
from ..base import StageResult
from .MonitorConfig import MonitorConfig


def cmd_filter_show(
    list_name: str | None = typer.Argument(
        None,
        help="Name of list to show (leave empty to list available)",
        show_default=False,
    ),
) -> StageResult:
    """Get contents of a monitor configuration list or list available names."""

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    if not isinstance(list_name, str) or not list_name:
        result = {"available_lists": list(MonitorConfig.get_filter_list_names()), "success": True}
        return StageResult(
            announce="Listing available monitor lists...",
            result="Available monitor lists",
            output=result,
        )

    if list_name not in MonitorConfig.get_filter_list_names():
        raise ValueError(f"Unknown list_name: {list_name!r}")

    items = getattr(monitor_cfg, list_name)
    result = {"list_name": list_name, "items": list(items), "count": len(items), "success": True}

    return StageResult(
        announce=f"Showing {list_name}...",
        result=f"Showing {list_name} ({result.get('count', 0)} items)",
        output=result,
    )
