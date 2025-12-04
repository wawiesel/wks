"""CLI display implementation using Rich library."""

import sys
from typing import Any, Dict, List, Optional

from ..constants import MAX_DISPLAY_WIDTH

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .base import Display


class CLIDisplay(Display):
    """Beautiful CLI display using Rich library."""

    def __init__(self):
        if not RICH_AVAILABLE:
            raise ImportError("Rich library required for CLI display. Install with: pip install rich")

        # Limit console width to MAX_DISPLAY_WIDTH for consistent display
        detected_width = None
        try:
            import shutil

            detected_width = shutil.get_terminal_size().columns
        except Exception:
            pass

        console_width = min(detected_width or MAX_DISPLAY_WIDTH, MAX_DISPLAY_WIDTH)
        self.console = Console(force_terminal=True, width=console_width)
        self.stderr_console = Console(file=sys.stderr, width=console_width)
        self._progress_contexts = {}  # Store Progress contexts by handle

    def status(self, message: str, **kwargs) -> None:
        """Display a status message in blue."""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def success(self, message: str, **kwargs) -> None:
        """Display a success message in green."""
        self.console.print(f"[green]✓[/green] {message}")

    def error(self, message: str, **kwargs) -> None:
        """Display an error message in red."""
        details = kwargs.get("details", "")
        if details:
            self.console.print(f"[red]✗[/red] {message}")
            self.console.print(f"  [dim]{details}[/dim]")
        else:
            self.console.print(f"[red]✗[/red] {message}")

    def warning(self, message: str, **kwargs) -> None:
        """Display a warning message in yellow."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def info(self, message: str, **kwargs) -> None:
        """Display an informational message."""
        self.console.print(message)

    def table(self, data: List[Dict[str, Any]], headers: Optional[List[str]] = None, **kwargs) -> None:
        """Display data in a rich table."""
        if not data:
            self.info("No data to display")
            return

        title = kwargs.get("title", "")
        column_justify = kwargs.get("column_justify", {})  # Dict[str, str] mapping header to justify
        show_header = kwargs.get("show_header", True)
        width = kwargs.get("width", MAX_DISPLAY_WIDTH)

        # Infer headers from first row if not provided
        if headers is None:
            headers = list(data[0].keys())

        table = Table(
            title=title,
            show_header=show_header,
            header_style="bold cyan",
            width=min(width, MAX_DISPLAY_WIDTH),
        )

        for header in headers:
            justify = column_justify.get(header, "left")
            table.add_column(header, justify=justify)

        for row in data:
            table.add_row(*[str(row.get(h, "")) for h in headers])

        self.console.print(table)

    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:
        """Start a progress bar (outputs to STDERR)."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.stderr_console,  # Progress goes to STDERR
        )
        progress.start()
        task_id = progress.add_task(description, total=total)

        # Store progress context with task_id
        handle = id(progress)
        self._progress_contexts[handle] = (progress, task_id)

        return handle

    def progress_update(self, handle: Any, advance: int = 1, **kwargs) -> None:
        """Update progress bar."""
        if handle not in self._progress_contexts:
            return

        progress, task_id = self._progress_contexts[handle]

        # Update description if provided
        description = kwargs.get("description")
        if description:
            progress.update(task_id, description=description, advance=advance)
        else:
            progress.update(task_id, advance=advance)

    def progress_finish(self, handle: Any, **kwargs) -> None:
        """Finish progress bar."""
        if handle not in self._progress_contexts:
            return

        progress, task_id = self._progress_contexts[handle]
        progress.stop()
        del self._progress_contexts[handle]

    def spinner_start(self, description: str = "", **kwargs) -> Any:
        """Start a spinner."""
        status = self.console.status(description, spinner="dots")
        status.start()
        return status

    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:
        """Update spinner description."""
        if handle:
            handle.update(description)

    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:
        """Stop spinner."""
        if handle:
            handle.stop()
        if message:
            self.info(message)

    def tree(self, data: Dict[str, Any], title: str = "", **kwargs) -> None:
        """Display hierarchical data as a tree."""
        tree = Tree(title if title else "Tree")
        self._build_tree(tree, data)
        self.console.print(tree)

    def _build_tree(self, tree: Tree, data: Any, key: str = "") -> None:
        """Recursively build tree structure."""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    branch = tree.add(f"[bold]{k}[/bold]")
                    self._build_tree(branch, v, k)
                else:
                    tree.add(f"{k}: {v}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    branch = tree.add(f"[dim][{i}][/dim]")
                    self._build_tree(branch, item)
                else:
                    tree.add(str(item))
        else:
            tree.add(str(data))

    def json_output(self, data: Any, **kwargs) -> None:
        """Output JSON with syntax highlighting."""
        import json

        indent = kwargs.get("indent", 2)
        json_str = json.dumps(data, indent=indent)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        self.console.print(syntax)

    def panel(self, content: Any, title: str = "", **kwargs) -> None:
        """Display content in a panel."""
        panel_kwargs = dict(kwargs)
        border_style = panel_kwargs.pop("border_style", "blue")
        panel = Panel(
            content,
            title=title,
            border_style=border_style,
            **panel_kwargs,
        )
        self.console.print(panel)
