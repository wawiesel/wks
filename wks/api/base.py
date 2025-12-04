"""Base utilities for WKS API module."""

import functools
import inspect
from typing import Any, Callable, Dict, List

import typer
from typer.core import TyperGroup
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
        if "config" in sig.parameters:
            if "config" not in kwargs:
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
            return MCPResult.error_result(
                str(e),
                details=traceback.format_exc()
            ).to_dict()

    return wrapper


def get_typer_command_schema(app: typer.Typer, command_name: str) -> Dict[str, Any]:
    """Generate MCP tool schema from a Typer command."""
    
    # This requires traversing the Typer app to find the command info
    # Typer stores commands in .registered_commands
    
    target_command = None
    for cmd_info in app.registered_commands:
        if cmd_info.name == command_name:
            target_command = cmd_info
            break
    
    if not target_command:
        raise ValueError(f"Command '{command_name}' not found in Typer app")

    # Extract schema
    # We need: description, inputSchema (type, properties, required)
    
    description = target_command.help or ""
    
    properties = {}
    required = []
    
    # Inspect function signature or Typer params
    # Typer stores param info in target_command.context_settings? No.
    # We might need to look at the callback function.
    
    func = target_command.callback
    if not func:
        return {}

    sig = inspect.signature(func)
    type_hints = inspect.gettypehints(func)
    
    for param_name, param in sig.parameters.items():
        if param_name == "config": # Skip injected config
            continue
            
        param_type = type_hints.get(param_name, str)
        
        # Map python types to JSON schema types
        json_type = "string"
        if param_type == int:
            json_type = "integer"
        elif param_type == bool:
            json_type = "boolean"
        elif param_type == float:
            json_type = "number"
        elif param_type == dict:
            json_type = "object"
        elif param_type == list:
            json_type = "array"
            
        prop_schema = {"type": json_type}
        
        # Check for default values (Typer Argument/Option)
        default = param.default
        description_text = ""
        
        if isinstance(default, (ArgumentInfo, OptionInfo)):
            if default.help:
                description_text = default.help
            # If it's an Option, it's usually optional unless required=True (which Argument defaults to)
            # Typer Argument default is ... (Ellipsis) means required
            
            if default.default == ...:
                required.append(param_name)
        elif default == inspect.Parameter.empty:
             required.append(param_name)
        
        if description_text:
            prop_schema["description"] = description_text
            
        properties[param_name] = prop_schema

    return {
        "name": f"wksm_{command_name.replace('-', '_')}", # Convention: wksm_ + command
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }
