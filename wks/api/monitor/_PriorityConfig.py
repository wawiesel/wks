from pydantic import BaseModel, Field, field_validator

from ._PriorityWeightsConfig import _PriorityWeightsConfig


class _PriorityConfig(BaseModel):
    """Priority configuration."""

    dirs: dict[str, float] = Field(...)
    weights: _PriorityWeightsConfig = Field(...)

    @field_validator("dirs")
    @classmethod
    def _normalize_dirs(cls, v: dict[str, float]) -> dict[str, float]:
        from wks.utils.normalize_path import normalize_path

        return {str(normalize_path(k)): val for k, val in v.items()}
