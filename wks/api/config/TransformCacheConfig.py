"""Transform cache configuration."""

from pydantic import BaseModel


class TransformCacheConfig(BaseModel):
    """Cache configuration for transform."""

    base_dir: str
    max_size_bytes: int
