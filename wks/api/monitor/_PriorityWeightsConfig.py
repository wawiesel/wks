"""Priority weights configuration."""

from pydantic import BaseModel, Field


class _PriorityWeightsConfig(BaseModel):
    """Priority weights configuration."""

    depth_multiplier: float = Field(0.9, gt=0.0)
    underscore_multiplier: float = Field(0.5, gt=0.0)
    only_underscore_multiplier: float = Field(0.1, gt=0.0)
    extension_weights: dict[str, float] = Field(default_factory=dict)
