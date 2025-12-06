"""Priority configuration."""

from pydantic import BaseModel, Field

from ._PriorityWeightsConfig import _PriorityWeightsConfig


class _PriorityConfig(BaseModel):
    """Priority configuration."""

    dirs: dict[str, float] = Field(default_factory=dict)
    weights: _PriorityWeightsConfig = Field(default_factory=_PriorityWeightsConfig)
