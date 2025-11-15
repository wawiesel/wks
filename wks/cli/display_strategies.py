"""Display strategies for service status output."""

import argparse
import sys
import time
from typing import Any, List, Optional, Tuple

from ..constants import MAX_DISPLAY_WIDTH
from ..service_controller import ServiceController, ServiceStatusData, ServiceStatusLaunch


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
        from rich.console import Console, Group
        from rich.live import Live
        from rich.table import Table
        from rich import box

        from ..constants import MAX_DISPLAY_WIDTH
        console = Console(width=MAX_DISPLAY_WIDTH)

        def _render_status():
            """Render current status as a Rich panel with Health left, File System right."""
            from rich.panel import Panel

            current_status = ServiceController.get_status()

            status_panel = self._status_panel(current_status, title="Status (Live)")
            renderables = [status_panel]
            launch_title, launch_content, launch_style = self._launch_panel_data(current_status.launch)
            renderables.append(
                Panel(launch_content, title=launch_title, border_style=launch_style, width=MAX_DISPLAY_WIDTH)
            )
            last_title, last_content, last_style = self._last_error_panel_data(current_status.last_error)
            renderables.append(
                Panel(last_content, title=last_title, border_style=last_style, width=MAX_DISPLAY_WIDTH)
            )
            notes_title, notes_content, notes_style = self._notes_panel_data(current_status.notes or [])
            renderables.append(
                Panel(notes_content, title=notes_title, border_style=notes_style, width=MAX_DISPLAY_WIDTH)
            )

            return Group(*renderables)

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
        status_panel = self._status_panel(status, title="Status")
        display.console.print(status_panel)
        self._render_launch_panel(display, status.launch)
        self._render_last_error_panel(display, status.last_error)
        self._render_notes_panel(display, status.notes or [])
        return 0

    @staticmethod
    def _last_error_panel_data(error_text: Optional[str]) -> Tuple[str, str, str]:
        content = error_text.strip() if error_text else "[dim]No recent errors[/dim]"
        return "Last Error", content, "red"

    @staticmethod
    def _notes_panel_data(notes: List[str]) -> Tuple[str, str, str]:
        if notes:
            content = "\n".join(f"• {note}" for note in notes)
        else:
            content = "[dim]No notes[/dim]"
        return "Notes", content, "cyan"

    @staticmethod
    def _launch_panel_data(launch: ServiceStatusLaunch) -> Tuple[str, Any, str]:
        from rich.table import Table

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", justify="left", style="magenta")
        table.add_column("Value", justify="right")

        if launch and launch.present():
            fields = [
                ("Type", launch.type),
                ("Path", launch.path),
                ("Program", launch.arguments or launch.program),
                ("Stdout", launch.stdout),
                ("Stderr", launch.stderr),
            ]
            for label, value in fields:
                table.add_row(label, value or "-")
        else:
            table.add_row("", "[dim]No launch agent data[/dim]")

        return "Launch Agent", table, "magenta"

    def _render_last_error_panel(self, display: Any, error_text: Optional[str]) -> None:
        """Render the last error in its own panel for readability."""
        title, content, style = self._last_error_panel_data(error_text)
        display.panel(content, title=title, border_style=style, width=MAX_DISPLAY_WIDTH)

    def _render_notes_panel(self, display: Any, notes: List[str]) -> None:
        """Render notes in a dedicated panel."""
        title, content, style = self._notes_panel_data(notes)
        display.panel(content, title=title, border_style=style, width=MAX_DISPLAY_WIDTH)

    def _render_launch_panel(self, display: Any, launch: ServiceStatusLaunch) -> None:
        """Render launch agent details in its own panel."""
        title, content, style = self._launch_panel_data(launch)
        display.panel(content, title=title, border_style=style, width=MAX_DISPLAY_WIDTH)

    @staticmethod
    def _status_panel(status: ServiceStatusData, title: str):
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns

        health_rows = status._build_health_rows()
        filesystem_rows = status._build_filesystem_rows()

        left_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        left_table.add_column("Key", justify="left", min_width=20, no_wrap=True)
        left_table.add_column("Value", justify="right", min_width=12)
        for key, value in health_rows:
            left_table.add_row(key, value)

        right_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        right_table.add_column("Key", justify="left", min_width=20, no_wrap=True)
        right_table.add_column("Value", justify="right", min_width=12)
        for key, value in filesystem_rows:
            right_table.add_row(key, value)

        columns = Columns([left_table, right_table], equal=True, expand=True)
        return Panel.fit(columns, title=title, border_style="cyan", width=MAX_DISPLAY_WIDTH)


def get_display_strategy(args: argparse.Namespace) -> DisplayStrategy:
    """Get appropriate display strategy based on args."""
    from .constants import DISPLAY_CHOICES

    display_mode = getattr(args, "display", None)
    if display_mode not in DISPLAY_CHOICES:
        raise ValueError(f"Invalid display mode: {display_mode!r}. Must be one of {DISPLAY_CHOICES}")

    if display_mode == "mcp":
        return MCPDisplayStrategy()

    return CLIDisplayStrategy()
