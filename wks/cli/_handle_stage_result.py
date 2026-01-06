"""Decorator to handle StageResult for CLI display."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from ._run_single_execution import _run_single_execution

if TYPE_CHECKING:
    import click

F = TypeVar("F", bound=Callable)


def _handle_stage_result(
    func: F,
    result_printer: Callable[[dict], None] | None = None,
    suppress_output: bool = False,
) -> F:
    """Wrap a command function to handle StageResult for CLI display.

    This wrapper handles the 4-stage pattern for CLI:
    1. Announce (print to stderr)
    2. Progress (if callback provided)
    3. Result (print to stderr)
    4. Output (print to stdout as JSON)

    Args:
        func: Function that returns StageResult

    Returns:
        Wrapped function that handles display and exits with appropriate code
    """

    def _extract_display_format() -> str:
        """Get the display format from the active Typer/Click context.

        Returns:
            The display format specified in the CLI context.

        Raises:
            RuntimeError: If no context is available or the flag was never set.
            ValueError: If an invalid display format value is encountered.
        """
        import click

        context: click.Context | None = click.get_current_context(silent=True)
        if context is None:
            raise RuntimeError("Display format unavailable: Typer context is missing")

        current: click.Context | None = context
        while current is not None:
            obj = current.obj
            if isinstance(obj, dict) and "display_format" in obj:
                value = obj["display_format"]
                if value in ("json", "yaml"):
                    return value
                raise ValueError(f"Invalid display_format value: {value!r}")
            current = current.parent

        raise RuntimeError("Display format not set in the Typer context chain")

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from wks.cli.display.display_context import display_context

        display = display_context.get_display("cli")

        try:
            display_format = _extract_display_format()
        except (RuntimeError, ValueError):
            # Default to yaml if context missing or format invalid
            display_format = "yaml"

        _run_single_execution(func, args, kwargs, display, display_format, result_printer, suppress_output)

    return wrapper  # type: ignore[return-value]
