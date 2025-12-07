"""CLI display implementation using Rich library."""

import sys
from typing import Any

try:
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


class ProgressContext:
    """Context manager for progress bars."""

    def __init__(self, display: "CLIDisplay", total: int, description: str = ""):
        self.display = display
        self.total = total
        self.description = description
        self.handle: Any | None = None

    def __enter__(self) -> "ProgressContext":
        """Start progress bar."""
        self.handle = self.display.progress_start(self.total, self.description)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finish progress bar."""
        if self.handle is not None:
            self.display.progress_finish(self.handle)
        return False

    def update(self, advance: int = 1, description: str | None = None) -> None:
        """Update progress within context.

        Args:
            advance: Number of items to advance (default: 1)
            description: Optional new description for the progress bar
        """
        if self.handle is not None:
            kwargs = {"description": description} if description else {}
            self.display.progress_update(self.handle, advance=advance, **kwargs)


class CLIDisplay(Display):
    """Beautiful CLI display using Rich library."""

    def __init__(self):
        if not RICH_AVAILABLE:
            raise ImportError("Rich library required for CLI display. Install with: pip install rich")

        # Use full terminal width (no truncation)
        # Main console outputs to stdout (for data output)
        self.console = Console(file=sys.stdout, force_terminal=True)
        # stderr console for status messages
        self.stderr_console = Console(file=sys.stderr)
        self._progress_contexts = {}  # Store Progress contexts by handle

    def status(self, message: str, **kwargs) -> None:  # noqa: ARG002
        """Display a status message in blue (to STDERR per CLI guidelines)."""
        self.stderr_console.print(f"[blue]i[/blue] {message}")

    def success(self, message: str, **kwargs) -> None:  # noqa: ARG002
        """Display a success message in green (to STDERR per CLI guidelines)."""
        self.stderr_console.print(f"[green]✓[/green] {message}")

    def error(self, message: str, **kwargs) -> None:
        """Display an error message in red (to STDERR per CLI guidelines)."""
        details = kwargs.get("details", "")
        if details:
            self.stderr_console.print(f"[red]✗[/red] {message}")
            self.stderr_console.print(f"  [dim]{details}[/dim]")
        else:
            self.stderr_console.print(f"[red]✗[/red] {message}")

    def warning(self, message: str, **kwargs) -> None:  # noqa: ARG002
        """Display a warning message in yellow (to STDERR per CLI guidelines)."""
        self.stderr_console.print(f"[yellow]⚠[/yellow] {message}")

    def info(self, message: str, **kwargs) -> None:  # noqa: ARG002
        """Display an informational message (to STDERR per CLI guidelines)."""
        self.stderr_console.print(message)

    def table(self, data: list[dict[str, Any]], headers: list[str] | None = None, **kwargs) -> None:
        """Display data in a rich table."""
        if not data:
            self.info("No data to display")
            return

        title = kwargs.get("title", "")
        column_justify = kwargs.get("column_justify", {})  # dict[str, str] mapping header to justify
        show_header = kwargs.get("show_header", True)
        width = kwargs.get("width", None)  # None = use full terminal width

        # Infer headers from first row if not provided
        if headers is None:
            headers = list(data[0].keys())

        table = Table(
            title=title,
            show_header=show_header,
            header_style="bold cyan",
            width=width,  # None = no width limit
        )

        for header in headers:
            justify = column_justify.get(header, "left")
            table.add_column(header, justify=justify)

        for row in data:
            table.add_row(*[str(row.get(h, "")) for h in headers])

        self.console.print(table)

    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:  # noqa: ARG002
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

    def progress_finish(self, handle: Any, **kwargs) -> None:  # noqa: ARG002
        """Finish progress bar."""
        if handle not in self._progress_contexts:
            return

        progress, task_id = self._progress_contexts[handle]
        # Ensure progress is at 100% before finishing
        task = progress.tasks[task_id]
        if task.total and task.completed < task.total:
            progress.update(task_id, completed=task.total)
        progress.stop()
        del self._progress_contexts[handle]

    def progress(self, total: int, description: str = "") -> ProgressContext:
        """Context manager for progress bars.

        Usage:
            with display.progress(total=10, description="Processing..."):
                for i in range(10):
                    # do work
                    display.progress_update(handle, advance=1)

        For simple operations that complete immediately:
            with display.progress(total=1, description="Working..."):
                result = do_work()
        """
        return ProgressContext(self, total, description)

    def spinner_start(self, description: str = "", **kwargs) -> Any:  # noqa: ARG002
        """Start a spinner."""
        status = self.console.status(description, spinner="dots")
        status.start()
        return status

    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:  # noqa: ARG002
        """Update spinner description."""
        if handle:
            handle.update(description)

    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:  # noqa: ARG002
        """Stop spinner."""
        if handle:
            handle.stop()
        if message:
            self.info(message)

    def tree(self, data: dict[str, Any], title: str = "", **kwargs) -> None:  # noqa: ARG002
        """Display hierarchical data as a tree."""
        tree = Tree(title if title else "Tree")
        self._build_tree(tree, data)
        self.console.print(tree)

    def _build_tree(self, tree: Tree, data: Any, key: str = "") -> None:  # noqa: ARG002
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
        """Output JSON or YAML with syntax highlighting in terminal, valid when redirected.

        Rich automatically detects when stdout is not a TTY and outputs plain text,
        ensuring valid JSON/YAML when redirected to a file.

        Args:
            data: Data to output
            format: Output format - "yaml" (default) or "json"
        """
        import json
        import sys

        output_format = kwargs.get("format", "yaml")
        indent = kwargs.get("indent", 2)

        if output_format == "yaml":
            try:
                import yaml
            except ImportError:
                raise ImportError("PyYAML required for YAML output. Install with: pip install pyyaml")

            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

            # Only use syntax highlighting if stdout is a TTY (interactive terminal)
            if sys.stdout.isatty():
                syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
                self.console.print(syntax)
            else:
                # Non-TTY: output raw YAML
                print(yaml_str, flush=True)
        else:
            # JSON output (default)
            json_str = json.dumps(data, indent=indent, ensure_ascii=False)

            # Only use syntax highlighting if stdout is a TTY (interactive terminal)
            if sys.stdout.isatty():
                syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
                self.console.print(syntax)
            else:
                # Non-TTY: output raw JSON
                print(json_str, flush=True)

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
