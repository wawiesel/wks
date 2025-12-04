"""Monitor check API function.

This function checks if a path would be monitored and calculates its priority.
Matches CLI: wksc monitor check <path>, MCP: wksm_monitor_check
"""

from typing import Any

import typer

from ...display.cli import CLIDisplay
from ...display.context import get_display
from ...monitor import MonitorController


def check(
    path: str = typer.Argument(..., help="File or directory path to check"),
) -> dict[str, Any]:
    """Check if a path would be monitored and calculate its priority.

    Args:
        path: File or directory path to check

    Returns:
        Dictionary with is_monitored, priority, and path information
    """
    from ...config import WKSConfig

    config = WKSConfig.load()

    display = get_display("cli")
    is_cli = isinstance(display, CLIDisplay)

    if is_cli:
        # Step 1: Announce
        display.status(f"Checking if path would be monitored: {path}")

        # Step 2: Progress
        with display.progress(total=1, description="Evaluating path..."):  # type: ignore[attr-defined]
            result = MonitorController.check_path(config.monitor, path)

        # Step 3: Result
        if result.get("is_monitored"):
            display.success(f"Path is monitored with priority {result.get('priority', 0)}")
        else:
            display.success("Path is not monitored")

        # Step 4: Output
        display.json_output(result)
    else:
        # MCP: Return data directly
        result = MonitorController.check_path(config.monitor, path)

    return result
