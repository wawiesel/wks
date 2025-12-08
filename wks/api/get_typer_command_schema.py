"""Extract JSON schema from Typer commands for MCP tool definitions."""

from typing import Any

import typer


def get_typer_command_schema(app: typer.Typer, command_name: str | None) -> dict:
    """Extract JSON schema from a Typer command for MCP tool definition.

    Args:
        app: Typer application
        command_name: Name of the command, or None for callback command

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

    # Handle callback command (command_name is None)
    if command_name is None:
        # For callback commands, check if app has a registered callback
        callback_info = getattr(app, "registered_callback", None)
        if callback_info and callback_info.callback:
            # Extract schema from callback function signature
            import inspect

            sig = inspect.signature(callback_info.callback)
            schema: dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            # Parse parameters from callback signature
            for param_name, param in sig.parameters.items():
                if param_name == "ctx":
                    continue  # Skip Typer context
                param_type = "string"  # Default type
                if param.annotation != inspect.Parameter.empty:
                    # Handle union types (e.g., str | None)
                    ann = param.annotation
                    if hasattr(ann, "__origin__") and ann.__origin__ is type(None) or (hasattr(ann, "__args__") and type(None) in ann.__args__):
                        # Extract the non-None type
                        if hasattr(ann, "__args__"):
                            ann = [a for a in ann.__args__ if a is not type(None)][0]
                    if ann == int or (hasattr(ann, "__origin__") and ann.__origin__ is int):
                        param_type = "integer"
                    elif ann == bool or (hasattr(ann, "__origin__") and ann.__origin__ is bool):
                        param_type = "boolean"
                    elif ann == float or (hasattr(ann, "__origin__") and ann.__origin__ is float):
                        param_type = "number"
                # Extract help text from Typer Argument/Option default
                description = ""
                if hasattr(param.default, "help"):
                    description = param.default.help
                elif hasattr(param.default, "default") and hasattr(param.default.default, "help"):
                    description = param.default.default.help
                schema["properties"][param_name] = {
                    "type": param_type,
                    "description": description,
                }
                # If parameter has a default value (not just a Typer Argument/Option), it's not required
                if param.default == inspect.Parameter.empty:
                    schema["required"].append(param_name)
            return schema

    raise ValueError(f"Command {command_name} not found in app")
