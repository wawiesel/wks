"""Base utilities for API functions."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

import typer


def inject_config(func: Callable) -> Callable:
    """Decorator to inject WKSConfig as first parameter if not provided."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Lazy import to avoid circular dependency
        from ..config import WKSConfig
        
        # Check if config is already provided
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # If first param is 'config' and it's not provided, inject it
        if param_names and param_names[0] == "config" and "config" not in kwargs and len(args) == 0:
            kwargs["config"] = WKSConfig.load()
        # If config is passed as positional arg, it's already there
        elif len(args) > 0 and param_names and param_names[0] == "config":
            pass  # Config already provided
        else:
            # Load config if needed
            config = WKSConfig.load()
            # Try to inject if function accepts config
            if param_names and param_names[0] == "config":
                kwargs["config"] = config

        return func(*args, **kwargs)

    return wrapper


class StageResult:
    """Result structure for 4-stage API pattern.

    API functions return this structure containing all 4 stages:
    - announce: Message for Step 1
    - progress: Generator or callback for Step 2 (optional)
    - result: Message for Step 3
    - output: Data for Step 4
    """

    def __init__(
        self,
        announce: str,
        result: str,
        output: dict[str, Any],
        progress_callback: Callable[[Callable], Any] | None = None,
        *,
        success: bool | None = None,
        progress_total: int | None = None,
    ):
        """Initialize 4-stage result.

        Args:
            announce: Message for Step 1 (Announce)
            result: Message for Step 3 (Result)
            output: Data for Step 4 (Output)
            progress_callback: Optional function that takes a progress update callback
                and executes work, calling the callback with progress updates
            success: Optional explicit success flag (falls back to output["success"])
            progress_total: Optional total units for progress reporting
        """
        self.announce = announce
        self.result = result
        self.output = output
        self.progress_callback = progress_callback
        self.progress_total = progress_total
        inferred_success = output.get("success", True) if isinstance(output, dict) else True
        self.success = inferred_success if success is None else success


def handle_stage_result(func: Callable) -> Callable:
    """Wrapper to execute StageResult and display output.
    
    This wrapper:
    1. Executes the function to get StageResult
    2. Executes progress callback if present
    3. Displays output using the display system
    4. Exits with appropriate code based on success
    
    Args:
        func: Function that returns a StageResult
        
    Returns:
        Wrapped function that displays StageResult output
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from ..display.context import get_display
        from ..display.format import data_to_tables
        
        display = get_display()
        result = func(*args, **kwargs)

        # If result is not a StageResult, return as-is (for backward compatibility)
        if not isinstance(result, StageResult):
            return result

        # Step 1: Announce
        if result.announce:
            display.status(result.announce)

        # Step 2: Progress (execute callback if present)
        if result.progress_callback:
            with display.progress(total=result.progress_total or 1, description=result.announce or "Processing..."):
                result.progress_callback(lambda *_args, **_kwargs: None)

        # Step 3: Result message
        if result.result:
            if result.success:
                display.success(result.result)
            else:
                display.error(result.result)

        # Step 4: Output (display tables)
        if result.output:
            tables = data_to_tables(result.output)
            for table in tables:
                display.table(
                    table["data"],
                    headers=table.get("headers"),
                    title=table.get("title", ""),
                )

        # Exit with appropriate code
        import sys
        sys.exit(0 if result.success else 1)

    return wrapper


def _find_typer_command(app: typer.Typer, command_name: str) -> Any:
    """Find a Typer command by name."""
    for cmd in app.registered_commands:
        if cmd.name == command_name:
            return cmd
    return None


def _map_python_type_to_json_schema(python_type: type) -> dict[str, Any]:
    """Map Python type to JSON Schema type."""
    type_mapping = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    # Handle Optional/Union types
    origin = getattr(python_type, "__origin__", None)
    if origin is not None:
        # Handle Optional[X] which is Union[X, None]
        args = getattr(python_type, "__args__", ())
        if len(args) >= 2 and type(None) in args:
            # Find the non-None type
            non_none_type = next((arg for arg in args if arg is not type(None)), args[0] if args else str)
            schema = _map_python_type_to_json_schema(non_none_type)
            return schema

    return type_mapping.get(python_type, {"type": "string"})


def _process_typer_parameter(
    param_name: str,  # noqa: ARG001
    param: inspect.Parameter,
    param_type: Any,
    default: Any,
) -> tuple[dict[str, Any], bool]:
    """Process a Typer parameter and return JSON schema property."""
    prop_schema = _map_python_type_to_json_schema(param_type)

    # Add description if available from Typer
    if hasattr(param, "help") and param.help:
        prop_schema["description"] = param.help

    # Mark as required if no default
    is_required = default is inspect.Parameter.empty

    return prop_schema, is_required


def get_typer_command_schema(app: typer.Typer, command_name: str) -> dict[str, Any]:
    """Generate MCP JSON schema from Typer command signature."""
    command = _find_typer_command(app, command_name)
    if not command:
        raise ValueError(f"Command {command_name} not found")

    func = command.callback
    sig = inspect.signature(func)

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        # Skip 'config' parameter (injected by decorator)
        if param_name == "config":
            continue

        param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
        default = param.default if param.default != inspect.Parameter.empty else inspect.Parameter.empty

        prop_schema, is_required = _process_typer_parameter(param_name, param, param_type, default)
        properties[param_name] = prop_schema

        if is_required:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required if required else None,
    }
