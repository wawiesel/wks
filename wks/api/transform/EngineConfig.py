"""Transform engine configuration."""

from typing import Any

from pydantic import BaseModel


class EngineConfig(BaseModel):
    """Single engine configuration."""

    type: str
    data: dict[str, Any] = {}
    supported_types: list[str] | None = None
