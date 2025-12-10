"""Output schema registry - separate module to avoid circular imports."""

from typing import Any

from pydantic import BaseModel

# Registry: maps (domain, command_name) -> schema class
# Example: ("daemon", "status") -> DaemonStatusOutput
_SCHEMA_REGISTRY: dict[tuple[str, str], type[BaseModel]] = {}


def register_output_schema(domain: str, command_name: str, schema_class: type[BaseModel]) -> None:
    """Register an output schema for a command.

    Args:
        domain: Domain name (e.g., "daemon", "config", "database")
        command_name: Command name without "cmd_" prefix (e.g., "status", "start")
        schema_class: Pydantic model class that defines the output structure
    """
    key = (domain, command_name)
    if key in _SCHEMA_REGISTRY:
        raise ValueError(f"Schema already registered for {domain}.{command_name}")
    _SCHEMA_REGISTRY[key] = schema_class


def get_output_schema(domain: str, command_name: str) -> type[BaseModel] | None:
    """Get the output schema for a command.

    Args:
        domain: Domain name (e.g., "daemon", "config", "database")
        command_name: Command name without "cmd_" prefix (e.g., "status", "start")

    Returns:
        Schema class if registered, None otherwise
    """
    return _SCHEMA_REGISTRY.get((domain, command_name))
