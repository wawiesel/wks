"""Base API utilities for WKS commands."""

import functools
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TypeVar

import typer

F = TypeVar("F", bound=Callable)


@dataclass
class StageResult:
    """Result from a command function following the 4-stage pattern.

    ALL fields are required. No exceptions.
    """

    announce: str
    progress_callback: Callable[[Callable[[str, float], None], "StageResult"], None]
    progress_total: int
    result: str = ""
    output: dict = None  # type: ignore[assignment]
    success: bool = False

    def __post_init__(self):
        """Initialize output dict."""
        if self.output is None:
            object.__setattr__(self, "output", {})


def _run_single_execution(
    func: F,
    args: tuple,
    kwargs: dict,
    display: Any,
    display_format: str,
) -> None:
    """Run command once and display result.

    Stage 1 (Announce) must happen IMMEDIATELY before any work starts.
    """
    # Stage 1: Announce - display IMMEDIATELY before calling function
    # We need to get announce first, so call function to get it, then do work in progress_callback
    # OR: function returns StageResult immediately with announce, work happens in progress_callback
    result = func(*args, **kwargs)

    # Stage 1: Announce - display IMMEDIATELY (announce is required, no hedging)
    display.status(result.announce)

    # Stage 2: Progress - REQUIRED for all commands
    # progress_callback is a generator that yields (progress_percent, message) tuples
    progress_gen = result.progress_callback(result)
    for progress_percent, message in progress_gen:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        display.info(f"[dim]{timestamp}[/dim] Progress: {message} ({progress_percent:.1%})")

    # Ensure required fields are set after callback completes
    if not result.result:
        raise ValueError("progress_callback must set result.result to a non-empty string")
    if not result.output:
        raise ValueError("progress_callback must set result.output to a non-empty dict")

    # Stage 3: Result
    if result.success:
        display.success(result.result)
    else:
        display.error(result.result)

    # Stage 4: Output - JSON or YAML based on --display flag
    display.json_output(result.output, format=display_format)

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


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
        # Get display context

        import typer

        from wks.api.display.context import get_display

        display = get_display("cli")

        # Get display format from Typer context if available
        display_format = "yaml"  # default
        try:
            ctx = typer.get_current_context(silent=True)
            while ctx:
                # Check ctx.obj first (Typer's standard way to store custom data)
                if hasattr(ctx, "obj") and ctx.obj and isinstance(ctx.obj, dict):
                    display_format = ctx.obj.get("display_format", display_format)
                    break
                # Fallback to ctx.meta for backwards compatibility
                if hasattr(ctx, "meta") and ctx.meta:
                    display_format = ctx.meta.get("display_format", display_format)
                    break
                # Try parent context
                ctx = getattr(ctx, "parent", None)
        except Exception:
            pass

        # Always single execution (live mode handled at CLI level)
        _run_single_execution(func, args, kwargs, display, display_format)

    return wrapper  # type: ignore[return-value]


def get_typer_command_schema(app: typer.Typer, command_name: str) -> dict:
    """Extract JSON schema from a Typer command for MCP tool definition.

    Args:
        app: Typer application
        command_name: Name of the command

    Returns:
        JSON schema dictionary
    """
    # Find the command
    for cmd in app.registered_commands:
        if cmd.name == command_name:
            # Extract schema from command info
            # This is a simplified version - full implementation would parse Typer's internal structure
            schema: dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            # TODO: Parse actual command parameters from Typer
            return schema

    raise ValueError(f"Command {command_name} not found in app")


def inject_config(func: F) -> F:
    """Decorator to inject WKSConfig as first parameter.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that automatically loads and injects config
    """

    def wrapper(*args, **kwargs):
        from ..config.WKSConfig import WKSConfig

        config = WKSConfig.load()
        return func(config, *args, **kwargs)

    return wrapper
