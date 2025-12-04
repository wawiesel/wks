"""Monitor validate API function.

This function validates monitor configuration for conflicts and issues.
Matches CLI: wksc monitor validate, MCP: wksm_monitor_validate
"""

from typing import Any

import typer

from ...display.cli import CLIDisplay
from ...display.context import get_display
from ...monitor import MonitorController


def validate() -> dict[str, Any]:
    """Validate monitor configuration for conflicts and issues.

    Returns:
        Dictionary with validation results including issues and redundancies
    """
    from ...config import WKSConfig

    config = WKSConfig.load()
    display = get_display("cli")
    is_cli = isinstance(display, CLIDisplay)

    if is_cli:
        # Step 1: Announce
        display.status("Validating monitor configuration...")

        # Step 2: Progress
        with display.progress(total=1, description="Checking for conflicts..."):  # type: ignore[attr-defined]
            result_obj = MonitorController.validate_config(config.monitor)
            result = result_obj.model_dump()

        # Step 3: Result
        if result.get("issues"):
            display.error(f"Found {len(result['issues'])} configuration issue(s)")
        else:
            display.success("Configuration is valid")

        # Step 4: Output
        display.json_output(result)
    else:
        # MCP: Return data directly
        result_obj = MonitorController.validate_config(config.monitor)
        result = result_obj.model_dump()

    # Exit with error code if there are issues (CLI only)
    if is_cli and result.get("issues"):
        raise typer.Exit(code=1)

    return result
