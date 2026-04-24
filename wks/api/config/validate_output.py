from collections.abc import Callable
from typing import Any

from .output_models import resolve_output_model


def validate_output(func: Callable, output: dict[str, Any]) -> dict[str, Any]:
    module_parts = func.__module__.split(".")
    if len(module_parts) < 3 or module_parts[0] != "wks" or module_parts[1] != "api":
        return output

    domain = module_parts[2]
    func_name = func.__name__
    if not func_name.startswith("cmd_"):
        return output

    command_name = func_name[4:]  # Remove "cmd_" prefix

    output_model_class = resolve_output_model(domain, command_name)
    if output_model_class is None:
        return output

    try:
        validated = output_model_class(**output)
        return validated.model_dump(mode="python")
    except Exception as e:
        raise ValueError(
            f"Output validation failed for {domain}.{command_name}: {e}\n"
            f"Expected schema: {output_model_class.model_json_schema()}\n"
            f"Got output: {output}"
        ) from e
