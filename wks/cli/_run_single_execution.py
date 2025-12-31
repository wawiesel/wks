"""Run command once and display result using 4-stage pattern."""

import sys
from collections.abc import Callable
from typing import Any, TypeVar

from wks.api.validate_output import validate_output

F = TypeVar("F", bound=Callable)


def _run_single_execution(
    func: F,
    args: tuple,
    kwargs: dict,
    display: Any,
    display_format: str,
    result_printer: Callable[[dict], None] | None = None,
    suppress_output: bool = False,
) -> None:
    """Run command once and display result.

    Stage 1 (Announce) must happen IMMEDIATELY before any work starts.
    Commands must handle all exceptions internally and format errors
    via their domain-specific output schema.
    """
    # Stage 1: Announce - display IMMEDIATELY before calling function
    result = func(*args, **kwargs)

    # Stage 1: Announce - display IMMEDIATELY (announce is required, no hedging)
    if not suppress_output:
        display.status(result.announce)

    # Stage 2: Progress - REQUIRED for all commands
    # progress_callback is a generator that yields (progress_percent, message) tuples
    progress_gen = result.progress_callback(result)
    for progress_percent, message in progress_gen:
        if not suppress_output:
            from datetime import datetime

            timestamp = datetime.now().strftime("%H:%M:%S")
            display.info(f"[dim]{timestamp}[/dim] Progress: {message} ({progress_percent:.1%})")

    # Ensure required fields are set after callback completes
    if not result.result:
        raise ValueError("progress_callback must set result.result to a non-empty string")
    if not result.output:
        raise ValueError("progress_callback must set result.output to a non-empty dict")

    # Validate output structure against schema (enforces consistent structure)
    try:
        result.output = validate_output(func, result.output)
    except ValueError as e:
        # Validation failure is a programming error - fail loudly
        raise ValueError(f"Output structure validation failed: {e}") from e

    # Stage 3: Result
    if not suppress_output:
        if result.success:
            display.success(result.result)
        else:
            display.error(result.result)

    # Stage 4: Output - JSON or YAML based on --display flag
    if result_printer:
        result_printer(result.output)
    elif not suppress_output:
        display.json_output(result.output, format=display_format)

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)
