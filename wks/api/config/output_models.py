"""Helpers for code-defined command output models."""

from __future__ import annotations

from functools import cache
from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from .BaseOutputSchema import BaseOutputSchema


def output_model(name: str, *required_fields: str) -> type[BaseModel]:
    """Create a command output model with required fields and standard errors/warnings."""
    fields = dict.fromkeys(required_fields, (Any, ...))
    return create_model(  # type: ignore[call-overload]
        name,
        __base__=BaseOutputSchema,
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


@cache
def resolve_output_model(domain: str, command_name: str) -> type[BaseModel] | None:
    """Resolve a command output model by domain and command name."""
    try:
        module = import_module(f"wks.api.{domain}")
    except ImportError:
        return None
    class_name = f"{domain.capitalize()}{_camelize(command_name)}Output"
    resolved = getattr(module, class_name, None)
    if isinstance(resolved, type) and issubclass(resolved, BaseModel):
        return resolved
    return None


def _camelize(text: str) -> str:
    """Convert snake_case command names to CamelCase."""
    return "".join(part.capitalize() for part in text.split("_") if part)
