"""Diff router configuration."""

from typing import Any

from pydantic import BaseModel, Field


class DiffRouterConfig(BaseModel):
    """Diff router configuration for engine selection."""

    rules: list[dict[str, Any]] = Field(default_factory=list)
    fallback: str = Field(default="text", min_length=1)
