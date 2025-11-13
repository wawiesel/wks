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

        console = Console()

        def _render_status() -> Table:
            """Render current status as a Rich table with grouped sections."""
            current_status = ServiceController.get_status()
            rows = current_status.to_rows()

            table = Table(
                title="WKS Service Status (Live)",
                header_style="bold cyan",
                box=box.SQUARE,
                expand=False,
                pad_edge=False,
                show_header=False,
            )
            table.add_column("", style="cyan", overflow="fold")
            table.add_column("", style="white", overflow="fold")

            for key, value in rows:
                if value == "" and not key.startswith("  "):
                    table.add_row(key, value, style="bold yellow")
                else:
                    table.add_row(key, value)

            return table

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
        table_data = []
        for key, value in rows:
            if value == "" and not key.startswith("  "):
                table_data.append({"Key": f"[bold yellow]{key}[/bold yellow]", "Value": value})
            else:
                table_data.append({"Key": key, "Value": value})
        display.table(table_data, title="WKS Service Status", column_justify={"Value": "left"})
        if status.notes:
            display.info("; ".join(status.notes))
        return 0


def get_display_strategy(args: argparse.Namespace) -> DisplayStrategy:
    """Get appropriate display strategy based on args."""
    from .constants import DISPLAY_CHOICES
    
    display_mode = getattr(args, "display", None)
    if display_mode not in DISPLAY_CHOICES:
        raise ValueError(f"Invalid display mode: {display_mode!r}. Must be one of {DISPLAY_CHOICES}")

    if display_mode == "mcp":
        return MCPDisplayStrategy()

    return CLIDisplayStrategy()

