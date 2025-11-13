"""Display strategies for service status output."""

import sys
import time
import argparse
from typing import Any

from ..service_controller import ServiceController, ServiceStatusData


class DisplayStrategy:
    """Base class for display strategies."""

    def render(self, status: ServiceStatusData, args: argparse.Namespace) -> int:
        """Render status using this strategy. Returns exit code."""
        raise NotImplementedError


class MCPDisplayStrategy(DisplayStrategy):
    """Strategy for MCP display mode."""

    def render(self, status: ServiceStatusData, args: argparse.Namespace) -> int:
        live = getattr(args, "live", False)
        if live:
            sys.stderr.write("--live mode is not supported with MCP display\n")
            raise ValueError("Live mode not supported with MCP")

        display = args.display_obj
        payload = status.to_dict()
        display.success("WKS service status", data=payload)
        return 0


class CLIDisplayStrategy(DisplayStrategy):
    """Strategy for CLI display mode."""

    def _render_live(self, status: ServiceStatusData, args: argparse.Namespace) -> int:
        """Render live-updating display mode."""
        from rich.console import Console
        from rich.live import Live
        from rich.table import Table
        from rich import box

        from ..constants import MAX_DISPLAY_WIDTH
        console = Console(width=MAX_DISPLAY_WIDTH)

        def _render_status():
            """Render current status as a Rich panel with Health left, File System right."""
            from rich.panel import Panel
            from rich.table import Table
            from rich.columns import Columns

            current_status = ServiceController.get_status()

            # Use the same layout as static display
            health_rows = current_status._build_health_rows()
            filesystem_rows = current_status._build_filesystem_rows()
            launch_rows = current_status._build_launch_rows()

            # Create left table (Health)
            left_table = Table(show_header=False, box=None, padding=(0, 1))
            left_table.add_column("Key", justify="left", width=22)
            left_table.add_column("Value", justify="right", width=10)
            for key, value in health_rows:
                left_table.add_row(key, value)

            # Add Launch section to left table if present
            if launch_rows:
                for key, value in launch_rows:
                    left_table.add_row(key, value)

            # Create right table (File System)
            right_table = Table(show_header=False, box=None, padding=(0, 1))
            right_table.add_column("Key", justify="left", width=22)
            right_table.add_column("Value", justify="right", width=10)
            for key, value in filesystem_rows:
                right_table.add_row(key, value)

            # Create side-by-side columns
            columns = Columns([left_table, right_table], equal=True)
            return Panel.fit(columns, title="WKS Service Status (Live)", border_style="cyan", width=MAX_DISPLAY_WIDTH)

        try:
            with Live(_render_status(), refresh_per_second=0.5, screen=False, console=console) as live:
                while True:
                    time.sleep(2.0)
                    try:
                        live.update(_render_status())
                    except Exception as update_exc:
                        console.print(f"[yellow]Warning: {update_exc}[/yellow]", end="")
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped monitoring.[/dim]")
            return 0
        except Exception as exc:
            console.print(f"[red]Error in live mode: {exc}[/red]")
            return 2

    def render(self, status: ServiceStatusData, args: argparse.Namespace) -> int:
        """Render status - either live or static based on args."""
        live = getattr(args, "live", False)
        if live:
            return self._render_live(status, args)

        display = args.display_obj
        rows = status.to_rows()
        # Use unified display function for consistent table formatting
        from .helpers import display_status_table
        display_status_table(display, rows, title="WKS Service Status")
        if status.notes:
            display.info("; ".join(status.notes))
        return 0


def _display_service_status(display: Any, status: ServiceStatusData) -> None:
    """Display service status with Health on left, File System on right."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from ..constants import MAX_DISPLAY_WIDTH

    health_rows = status._build_health_rows()
    filesystem_rows = status._build_filesystem_rows()
    launch_rows = status._build_launch_rows()

    # Create left table (Health)
    left_table = Table(show_header=False, box=None, padding=(0, 1))
    left_table.add_column("Key", justify="left", width=22)
    left_table.add_column("Value", justify="right", width=10)
    for key, value in health_rows:
        left_table.add_row(key, value)

    # Add Launch section to left table if present
    if launch_rows:
        for key, value in launch_rows:
            left_table.add_row(key, value)

    # Create right table (File System)
    right_table = Table(show_header=False, box=None, padding=(0, 1))
    right_table.add_column("Key", justify="left", width=22)
    right_table.add_column("Value", justify="right", width=10)
    for key, value in filesystem_rows:
        right_table.add_row(key, value)

    # Create side-by-side columns
    columns = Columns([left_table, right_table], equal=True)

    # Display in panel
    panel = Panel.fit(columns, title="WKS Service Status", border_style="cyan", width=MAX_DISPLAY_WIDTH)
    display.console.print(panel)


def get_display_strategy(args: argparse.Namespace) -> DisplayStrategy:
    """Get appropriate display strategy based on args."""
    from .constants import DISPLAY_CHOICES

    display_mode = getattr(args, "display", None)
    if display_mode not in DISPLAY_CHOICES:
        raise ValueError(f"Invalid display mode: {display_mode!r}. Must be one of {DISPLAY_CHOICES}")

    if display_mode == "mcp":
        return MCPDisplayStrategy()

    return CLIDisplayStrategy()
