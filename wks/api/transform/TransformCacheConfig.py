"""Transform cache configuration."""

from pydantic import BaseModel, Field, field_validator


class TransformCacheConfig(BaseModel):
    """Cache configuration for transform."""

    base_dir: str
    max_size_bytes: int = Field(..., gt=0, description="Max cache size in bytes (must be > 0)")

    @field_validator("base_dir")
    @classmethod
    def _normalize_base_dir(cls, v: str) -> str:
        from wks.utils.normalize_path import normalize_path

        return str(normalize_path(v))
