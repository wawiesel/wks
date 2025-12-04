"""Monitor show API function.

This function gets the contents of a monitor configuration list or, if no list
is specified, returns the available list names.
Matches CLI: wksc monitor show [<list-name>], MCP: wksm_monitor_show
"""

import typer

from ...config import WKSConfig
from ...monitor import MonitorController
from ..base import StageResult

LIST_NAMES = (
    "include_paths",
    "exclude_paths",
    "include_dirnames",
    "exclude_dirnames",
    "include_globs",
    "exclude_globs",
)


def cmd_show(
    list_name: str | None = typer.Argument(
        None,
        help="Name of list to show (leave empty to list available)",
        show_default=False,
    ),
) -> StageResult:
    """Get contents of a monitor configuration list or list available names."""

    config = WKSConfig.load()

    if not isinstance(list_name, str) or not list_name:
        result = {"available_lists": list(LIST_NAMES), "success": True}
        return StageResult(
            announce="Listing available monitor lists...",
            result="Available monitor lists",
            output=result,
        )

    result = MonitorController.get_list(config.monitor, list_name)

    return StageResult(
        announce=f"Showing {list_name}...",
        result=f"Showing {list_name} ({result.get('count', 0)} items)",
        output=result,
    )

