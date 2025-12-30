"""Transform configuration for WKSConfig."""

from pydantic import BaseModel

from ._CacheConfig import _CacheConfig
from ._EngineConfig import _EngineConfig


class TransformConfig(BaseModel):
    """Transform section of WKS configuration."""

    cache: _CacheConfig
    engines: dict[str, _EngineConfig]
