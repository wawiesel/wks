"""Output schemas for API commands - enforces consistent output structure.

Each command must have a Pydantic model that defines its output structure.
All fields must always be present (even if empty/null) to ensure consistency.
"""

from collections.abc import Callable
from typing import Any

from ..schema_registry import schema_registry


def validate_output(func: Callable, output: dict[str, Any]) -> dict[str, Any]:
    """Validate output dict against registered schema.

    Args:
        func: The command function (used to infer domain and command name)
        output: The output dict to validate

    Returns:
        Validated output dict (with defaults filled in)

    Raises:
        ValueError: If validation fails
    """
    # Infer domain and command from function
    module_parts = func.__module__.split(".")
    if len(module_parts) < 3 or module_parts[0] != "wks" or module_parts[1] != "api":
        # Not an API function, skip validation
        return output

    domain = module_parts[2]
    func_name = func.__name__
    if not func_name.startswith("cmd_"):
        # Not a command function, skip validation
        return output

    command_name = func_name[4:]  # Remove "cmd_" prefix

    schema_class = schema_registry.get_output_schema(domain, command_name)
    if schema_class is None:
        # No schema registered, skip validation (but warn in development?)
        return output

    # Validate and coerce output
    try:
        validated = schema_class(**output)
        # Use model_dump with mode='python' to get native Python types
        return validated.model_dump(mode="python")
    except Exception as e:
        raise ValueError(
            f"Output validation failed for {domain}.{command_name}: {e}\n"
            f"Expected schema: {schema_class.model_json_schema()}\n"
            f"Got output: {output}"
        ) from e
