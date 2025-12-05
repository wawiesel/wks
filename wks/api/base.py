"""Base API utilities for WKS commands."""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import typer


@dataclass
class StageResult:
    """Result from a command function following the 4-stage pattern.

    Attributes:
        announce: Initial status message (Stage 1)
        result: Final result message (Stage 3)
        output: Structured output data (Stage 4)
        success: Whether the operation succeeded (inferred from output if not provided)
        progress_callback: Optional callback for progress updates (Stage 2)
        progress_total: Total items for progress tracking
    """

    announce: str
    result: str
    output: dict[str, Any]
    success: bool | None = None
    progress_callback: Callable[[Callable], None] | None = None
    progress_total: int | None = None

    def __post_init__(self):
        """Infer success from output if not explicitly set."""
        if self.success is None:
            # Infer success from output dict if it has a 'success' key
            if isinstance(self.output, dict) and "success" in self.output:
                self.success = bool(self.output["success"])
            else:
                # Default to True if no success indicator
                self.success = True


def handle_stage_result(func: Callable[[], StageResult]) -> Callable[[], Any]:
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
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)

        # Stage 1: Announce
        print(result.announce, file=sys.stderr)

        # Stage 2: Progress (if callback provided)
        if result.progress_callback:
            result.progress_callback(lambda msg, progress: print(f"Progress: {msg} ({progress:.1%})", file=sys.stderr))

        # Stage 3: Result
        print(result.result, file=sys.stderr)

        # Stage 4: Output (JSON to stdout)
        import json
        print(json.dumps(result.output, indent=2))

        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    return wrapper


def get_typer_command_schema(app: typer.Typer, command_name: str) -> dict[str, Any]:
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


def inject_config(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to inject WKSConfig as first parameter.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function that automatically loads and injects config
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from ..config import WKSConfig
        config = WKSConfig.load()
        return func(config, *args, **kwargs)
    return wrapper
