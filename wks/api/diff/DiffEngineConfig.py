"""Diff engine configuration."""

from typing import Any

from pydantic import BaseModel, Field


class DiffEngineConfig(BaseModel):
    """Diff engine-specific configuration.

    The engine name is the key in the engines dictionary.
    """

    enabled: bool = False
    is_default: bool = False
    options: dict[str, Any] = Field(default_factory=dict)
