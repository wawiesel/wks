"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from typing import Any

from ...config import WKSConfig
from ...display.cli import CLIDisplay
from ...display.context import get_display
from ...monitor import MonitorController
from ..base import inject_config


@inject_config
def status(config: WKSConfig) -> dict[str, Any]:
    """Get filesystem monitoring status and configuration.

    Returns monitor status including tracked files count, configuration
    issues, redundancies, and all monitor configuration lists.

    Args:
        config: WKS configuration (injected)

    Returns:
        Dictionary with monitor status data
    """
    display = get_display("cli")
    is_cli = isinstance(display, CLIDisplay)

    if is_cli:
        # Step 1: Announce
        display.status("Checking monitor status...")

        # Step 2: Progress
        # Type ignore: CLIDisplay has progress() method, but Display base doesn't
        with display.progress(total=1, description="Querying monitor database..."):  # type: ignore[attr-defined]
            status_obj = MonitorController.get_status(config.monitor)
            result = status_obj.model_dump()

        # Step 3: Result
        display.success("Monitor status retrieved")

        # Step 4: Output
        display.json_output(result)
    else:
        # MCP: Return data directly
        status_obj = MonitorController.get_status(config.monitor)
        result = status_obj.model_dump()

    return result
