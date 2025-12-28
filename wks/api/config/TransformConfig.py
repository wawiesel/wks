"""Transform configuration for WKSConfig."""

from pydantic import BaseModel

from .TransformCacheConfig import TransformCacheConfig
from .TransformEngineConfig import TransformEngineConfig


class TransformConfig(BaseModel):
    """Transform section of WKS configuration."""

    cache: TransformCacheConfig
    engines: dict[str, TransformEngineConfig]
