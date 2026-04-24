import sys
from collections.abc import Sequence
from typing import Any, TypeAlias

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .Display import Display

StyledSegment: TypeAlias = tuple[str, str | None]


class CLIDisplay(Display):
    class ProgressContext:
        def __init__(self, display: "CLIDisplay", total: int, description: str = ""):
            self.display = display
            self.total = total
            self.description = description
            self.handle: Any | None = None

        def __enter__(self) -> "CLIDisplay.ProgressContext":
            self.handle = self.display.progress_start(self.total, self.description)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.handle is not None:
                self.display.progress_finish(self.handle)
            return False

        def update(self, advance: int = 1, description: str | None = None) -> None:
            if self.handle is not None:
                kwargs = {"description": description} if description else {}
                self.display.progress_update(self.handle, advance=advance, **kwargs)

    def __init__(self):
        if not RICH_AVAILABLE:
            raise ImportError("Rich library required for CLI display. Install with: pip install rich")

        self._original_stdout = sys.stdout
        self.console = Console(file=sys.stdout)
        self.stderr_console = Console(file=sys.stderr)
        self._progress_contexts = {}

    def _stderr_line(
        self,
        *,
        icon: str,
        icon_style: str,
        message: str,
        segments: Sequence[StyledSegment] = (),
    ) -> None:
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        if not segments:
            self.stderr_console.print(
                f"[dim]{timestamp}[/dim] [{icon_style}]{icon}[/{icon_style}] {message}",
                soft_wrap=True,
            )
            return

        line = Text()
        line.append(timestamp, style="dim")
        line.append(" ")
        line.append(icon, style=icon_style)
        line.append(" ")
        for text, style in segments:
            if style:
                line.append(text, style=style)
            else:
                line.append(text)
        self.stderr_console.print(line, soft_wrap=True, highlight=False)

    def status(self, message: str, **kwargs) -> None:
        self._stderr_line(
            icon="i",
            icon_style="blue",
            message=message,
            segments=kwargs.get("segments", ()),
        )

    def success(self, message: str, **kwargs) -> None:
        self._stderr_line(
            icon="✓",
            icon_style="green",
            message=message,
            segments=kwargs.get("segments", ()),
        )

    def error(self, message: str, **kwargs) -> None:
        details = kwargs.get("details", "")
        segments = kwargs.get("segments", ())
        if details:
            self._stderr_line(icon="✗", icon_style="red", message=message, segments=segments)
            self.stderr_console.print(f"  [dim]{details}[/dim]", soft_wrap=True)
        else:
            self._stderr_line(icon="✗", icon_style="red", message=message, segments=segments)

    def warning(self, message: str, **kwargs) -> None:  # noqa: ARG002
        self.stderr_console.print(f"[yellow]⚠[/yellow] {message}", soft_wrap=True)

    def info(self, message: str, **kwargs) -> None:  # noqa: ARG002
        self.stderr_console.print(message, soft_wrap=True)

    def progress_start(self, total: int, description: str = "", **kwargs) -> Any:  # noqa: ARG002
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.stderr_console,
        )
        progress.start()
        task_id = progress.add_task(description, total=total)

        handle = id(progress)
        self._progress_contexts[handle] = (progress, task_id)

        return handle

    def progress_update(self, handle: Any, advance: int = 1, **kwargs) -> None:
        if handle not in self._progress_contexts:
            return

        progress, task_id = self._progress_contexts[handle]

        description = kwargs.get("description")
        if description:
            progress.update(task_id, description=description, advance=advance)
        else:
            progress.update(task_id, advance=advance)

    def progress_finish(self, handle: Any, **kwargs) -> None:  # noqa: ARG002
        if handle not in self._progress_contexts:
            return

        progress, task_id = self._progress_contexts[handle]
        task = progress.tasks[task_id]
        if task.total and task.completed < task.total:
            progress.update(task_id, completed=task.total)
        progress.stop()
        del self._progress_contexts[handle]

    def progress(self, total: int, description: str = "") -> "CLIDisplay.ProgressContext":
        return CLIDisplay.ProgressContext(self, total, description)

    def spinner_start(self, description: str = "", **kwargs) -> Any:  # noqa: ARG002
        status = self.console.status(description, spinner="dots")
        status.start()
        return status

    def spinner_update(self, handle: Any, description: str, **kwargs) -> None:  # noqa: ARG002
        if handle:
            handle.update(description)

    def spinner_finish(self, handle: Any, message: str = "", **kwargs) -> None:  # noqa: ARG002
        if handle:
            handle.stop()
        if message:
            self.info(message)

    def json_output(self, data: Any, **kwargs) -> None:
        import json
        import sys

        output_format = kwargs.get("format", "yaml")
        indent = kwargs.get("indent", 2)

        if output_format == "yaml":
            try:
                import yaml  # type: ignore
            except ImportError:
                raise ImportError("PyYAML required for YAML output. Install with: pip install pyyaml") from None

            yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
            if sys.stdout.isatty():
                try:
                    from pygments import highlight
                    from pygments.formatters import Terminal256Formatter
                    from pygments.lexers import YamlLexer

                    highlighted = highlight(yaml_str, YamlLexer(), Terminal256Formatter(style="monokai"))
                    print(highlighted, end="")
                except ImportError:
                    print(yaml_str, end="")
            else:
                print(yaml_str, end="")
        else:
            json_str = json.dumps(data, indent=indent, ensure_ascii=False)
            if sys.stdout.isatty():
                try:
                    from pygments import highlight
                    from pygments.formatters import Terminal256Formatter
                    from pygments.lexers import JsonLexer

                    highlighted = highlight(json_str, JsonLexer(), Terminal256Formatter(style="monokai"))
                    print(highlighted, end="")
                except ImportError:
                    print(json_str, file=sys.stdout)
            else:
                print(json_str, file=sys.stdout)
