"""Transform engine configuration."""

from typing import Any

from pydantic import BaseModel


class TransformEngineConfig(BaseModel):
    """Single engine configuration."""

    type: str
    data: dict[str, Any] = {}
