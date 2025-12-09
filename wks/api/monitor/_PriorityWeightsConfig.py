"""Priority weights configuration."""

from pydantic import BaseModel, Field


class _PriorityWeightsConfig(BaseModel):
    """Priority weights configuration."""

    depth_multiplier: float = Field(..., gt=0.0)
    underscore_multiplier: float = Field(..., gt=0.0)
    only_underscore_multiplier: float = Field(..., gt=0.0)
    extension_weights: dict[str, float] = Field(...)
