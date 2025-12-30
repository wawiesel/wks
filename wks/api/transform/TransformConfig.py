"""Transform configuration for WKSConfig."""

from pydantic import BaseModel

from .CacheConfig import CacheConfig
from .EngineConfig import EngineConfig


class TransformConfig(BaseModel):
    """Transform section of WKS configuration."""

    cache: CacheConfig
    engines: dict[str, EngineConfig]
