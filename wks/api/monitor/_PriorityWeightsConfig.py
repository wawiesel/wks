from pydantic import BaseModel, Field


class _PriorityWeightsConfig(BaseModel):
    depth_multiplier: float = Field(..., gt=0.0)
    underscore_multiplier: float = Field(..., gt=0.0)
    only_underscore_multiplier: float = Field(..., gt=0.0)
    extension_weights: dict[str, float] = Field(...)
