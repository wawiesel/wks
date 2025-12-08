"""Decorator to handle StageResult for CLI display."""

import functools
from collections.abc import Callable
from typing import TypeVar

import typer

from ._run_single_execution import _run_single_execution

F = TypeVar("F", bound=Callable)


def handle_stage_result(func: F) -> F:
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

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from wks.utils.display.context import get_display
        import click

        display = get_display("cli")

        # Get display format from Click/Typer context (json or yaml)
        # Walk up context tree to find display_format set by main_callback
        display_format = "yaml"  # default
        try:
            ctx = click.get_current_context(silent=True)
            while ctx:
                if hasattr(ctx, "obj") and ctx.obj and isinstance(ctx.obj, dict):
                    format_val = ctx.obj.get("display_format")
                    # If found and valid, use it and stop
                    if format_val in ("json", "yaml"):
                        display_format = format_val
                        break
                # Continue to parent context if not found
                ctx = getattr(ctx, "parent", None)
        except Exception:
            pass

        _run_single_execution(func, args, kwargs, display, display_format)

    return wrapper  # type: ignore[return-value]
