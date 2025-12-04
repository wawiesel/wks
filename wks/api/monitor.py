"""Monitor API - Basic monitor operations."""

from typing import Any

import typer

from ..config import WKSConfig
from ..mcp.result import MCPResult
from ..monitor import MonitorController
from .base import display_output, inject_config

monitor_app = typer.Typer(name="monitor", help="Monitor operations")


@monitor_app.command(name="status")
@inject_config
@display_output
def monitor_status(config: WKSConfig) -> dict[str, Any]:
    """Get filesystem monitoring status and configuration."""
    status = MonitorController.get_status(config.monitor)
    return MCPResult(success=True, data=status.model_dump()).to_dict()


@monitor_app.command(name="check")
@inject_config
@display_output
def monitor_check(
    path: str = typer.Argument(..., help="File or directory path to check"),
    config: WKSConfig | None = None,  # injected
) -> dict[str, Any]:
    """Check if a path would be monitored and calculate its priority."""
    if config is None:
        raise ValueError("config must be provided")
    result = MonitorController.check_path(config.monitor, path)
    return MCPResult(success=True, data=result).to_dict()


@monitor_app.command(name="validate")
@inject_config
@display_output
def monitor_validate(config: WKSConfig) -> dict[str, Any]:
    """Validate monitor configuration for conflicts and issues."""
    result = MonitorController.validate_config(config.monitor)
    return MCPResult(success=True, data=result.model_dump()).to_dict()
