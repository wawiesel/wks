"""Transform configuration for WKSConfig."""

from pydantic import BaseModel, model_validator

from ._CacheConfig import _CacheConfig
from ._EngineConfig import _EngineConfig


class TransformConfig(BaseModel):
    """Transform section of WKS configuration."""

    cache: _CacheConfig
    default_engine: str
    engines: dict[str, _EngineConfig]

    @model_validator(mode="after")
    def validate_default_engine_exists(self) -> "TransformConfig":
        """Require default_engine to reference a configured engine."""
        if self.default_engine not in self.engines:
            raise ValueError(
                f"transform.default_engine '{self.default_engine}' must reference a configured engine "
                f"(available: {list(self.engines.keys())})"
            )
        return self
