"""Diff configuration root model."""

from pydantic import BaseModel, Field, model_validator

from .DiffEngineConfig import DiffEngineConfig
from .DiffRouterConfig import DiffRouterConfig


class DiffConfig(BaseModel):
    """Diff configuration."""

    engines: dict[str, DiffEngineConfig]
    router: DiffRouterConfig = Field(alias="_router", default_factory=DiffRouterConfig)

    @model_validator(mode="after")
    def validate_default_engine(self) -> "DiffConfig":
        """Ensure at least one engine is marked as default."""
        if not any(eng.is_default for eng in self.engines.values()):
            raise ValueError("At least one engine must be marked as default (is_default=True)")
        return self
