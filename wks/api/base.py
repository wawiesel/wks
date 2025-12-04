"""Base utilities for WKS API module."""

import functools
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

import typer
from typer.models import ArgumentInfo, OptionInfo

from ..config import WKSConfig
from ..mcp.result import MCPResult


def inject_config(func: Callable) -> Callable:
    """Decorator to inject WKSConfig into the function."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if config is already in kwargs or args
        # This is a simple check; for robust injection we might need signature inspection
        # But usually we just call these functions.
        # Typer might interfere if we change signature, but we will handle that.

        # If called from Typer, it handles arguments. We need to inject config if it's expected.
        # If called manually (e.g. from MCP), we can pass config manually or let this inject.

        # Actually, for Typer, dependency injection is usually done via typer.Context or depends.
        # But here we want a simple decorator.

        sig = inspect.signature(func)
        if "config" in sig.parameters and "config" not in kwargs:
            # If config is not passed, load it
            # Note: If args are passed positionally, we need to be careful.
            # Assuming 'config' is usually the first argument if present, or passed as kwarg.
            try:
                kwargs["config"] = WKSConfig.load()
            except Exception as e:
                # If config fails to load, what do we do?
                # For now, let it bubble up or handle gracefully?
                # The requirement says "Fail fast".
                raise e

        return func(*args, **kwargs)

    return wrapper


def display_output(func: Callable) -> Callable:
    """Decorator to handle output formatting (JSON/Table) and error handling."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            # If result is MCPResult, return it directly (MCP server handles formatting)
            # If CLI, we might print. But scope says CLI integration is later.
            # So just return result.
            return result
        except Exception as e:
            # Return structured error result
            # This helps MCP server return clean errors
            import traceback

            return MCPResult.error_result(str(e), details=traceback.format_exc()).to_dict()

    return wrapper


def _find_typer_command(app: typer.Typer, command_name: str) -> Any:
    """Find a Typer command by name."""
    for cmd_info in app.registered_commands:
        if cmd_info.name == command_name:
            return cmd_info
    raise ValueError(f"Command '{command_name}' not found in Typer app")


def _map_python_type_to_json_schema(param_type: Any) -> str:
    """Map Python type to JSON schema type."""
    if param_type is int:
        return "integer"
    if param_type is bool:
        return "boolean"
    if param_type is float:
        return "number"
    if param_type is dict:
        return "object"
    if param_type is list:
        return "array"
    return "string"


def _process_typer_parameter(
    param_name: str,  # noqa: ARG001
    param: inspect.Parameter,  # noqa: ARG001
    param_type: Any,
    default: Any,
) -> tuple[dict[str, Any], bool]:
    """Process a Typer parameter and return schema and required flag."""
    json_type = _map_python_type_to_json_schema(param_type)
    prop_schema = {"type": json_type}
    description_text = ""
    is_required = False

    if isinstance(default, (ArgumentInfo, OptionInfo)):
        if default.help:
            description_text = default.help
        if default.default == ...:
            is_required = True
    elif default == inspect.Parameter.empty:
        is_required = True

    if description_text:
        prop_schema["description"] = description_text

    return prop_schema, is_required


def get_typer_command_schema(app: typer.Typer, command_name: str) -> dict[str, Any]:
    """Generate MCP tool schema from a Typer command."""
    target_command = _find_typer_command(app, command_name)
    description = target_command.help or ""

    func = target_command.callback
    if not func:
        return {}

    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name == "config":  # Skip injected config
            continue

        param_type = type_hints.get(param_name, str)
        prop_schema, is_required = _process_typer_parameter(param_name, param, param_type, param.default)

        if is_required:
            required.append(param_name)

        properties[param_name] = prop_schema

    return {
        "name": f"wksm_{command_name.replace('-', '_')}",  # Convention: wksm_ + command
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required},
    }
