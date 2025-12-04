"""Monitor API - Basic monitor operations."""

from typing import Any

import typer

from ..config import WKSConfig
from ..display.context import get_display
from ..monitor import MonitorController
from .base import inject_config

monitor_app = typer.Typer(
    name="monitor",
    help="Monitor operations",
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@monitor_app.command(name="status")
@inject_config
def monitor_status(config: WKSConfig) -> dict[str, Any]:
    """Get filesystem monitoring status and configuration."""
    status = MonitorController.get_status(config.monitor)
    result = status.model_dump()
    # Display result when called from CLI
    display = get_display("cli")
    display.json_output(result)
    return result


@monitor_app.command(name="check")
@inject_config
def monitor_check(
    path: str = typer.Argument(..., help="File or directory path to check"),
    config: WKSConfig | None = None,  # injected
) -> dict[str, Any]:
    """Check if a path would be monitored and calculate its priority."""
    if config is None:
        raise ValueError("config must be provided")
    result = MonitorController.check_path(config.monitor, path)
    # Display result when called from CLI
    display = get_display("cli")
    display.json_output(result)
    return result


@monitor_app.command(name="validate")
@inject_config
def monitor_validate(config: WKSConfig) -> dict[str, Any]:
    """Validate monitor configuration for conflicts and issues."""
    result = MonitorController.validate_config(config.monitor)
    result_dict = result.model_dump()
    # Display result when called from CLI
    display = get_display("cli")
    display.json_output(result_dict)
    # Exit with error code if there are issues
    if result_dict.get("issues"):
        raise typer.Exit(code=1)
    return result_dict
