from typing import Any

from pydantic import BaseModel, Field


class _EngineConfig(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    supported_types: list[str] | None = None
