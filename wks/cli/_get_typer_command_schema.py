"""Extract JSON schema from Typer commands for MCP tool definitions."""

import inspect
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

    def extract_non_none_type(annotation: Any) -> Any:
        """Extract the non-None type from a union type annotation."""
        if hasattr(annotation, "__args__") and type(None) in annotation.__args__:
            return next(a for a in annotation.__args__ if a is not type(None))
        return annotation

    def check_type_match(ann: Any, target_type: type) -> bool:
        """Check if annotation matches target type."""
        return ann is target_type or (hasattr(ann, "__origin__") and ann.__origin__ is target_type)

    def get_param_type(annotation: Any) -> str:
        """Determine JSON schema type from Python type annotation."""
        if annotation == inspect.Parameter.empty:
            return "string"
        ann = extract_non_none_type(annotation)

        if check_type_match(ann, int):
            return "integer"
        if check_type_match(ann, bool):
            return "boolean"
        if check_type_match(ann, float):
            return "number"
        return "string"

    def get_param_description(param: inspect.Parameter) -> str:
        """Extract help text from Typer Argument/Option default."""
        if hasattr(param.default, "help"):
            return param.default.help
        if hasattr(param.default, "default") and hasattr(param.default.default, "help"):
            return param.default.default.help
        return ""

    def build_callback_schema(callback_info: Any) -> dict[str, Any]:
        """Build JSON schema from callback function signature."""
        sig = inspect.signature(callback_info.callback)
        callback_schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        for param_name, param in sig.parameters.items():
            if param_name == "ctx":
                continue
            param_type = get_param_type(param.annotation)
            description = get_param_description(param)
            callback_schema["properties"][param_name] = {
                "type": param_type,
                "description": description,
            }
            if param.default == inspect.Parameter.empty:
                callback_schema["required"].append(param_name)
        return callback_schema

    # Find the command
    for cmd in app.registered_commands:
        if cmd.name == command_name:
            return build_callback_schema(cmd)

    # Handle callback command (command_name is None)
    if command_name is None:
        callback_info = getattr(app, "registered_callback", None)
        if callback_info and callback_info.callback:
            return build_callback_schema(callback_info)

    raise ValueError(f"Command {command_name} not found in app")
