"""Daemon configuration (simple, required fields only)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    model_config = ConfigDict(extra="forbid")

    sync_interval_secs: float = Field(..., gt=0, description="Interval to poll/flush filesystem events")

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            raise ValueError(f"daemon config must be a dict, got {type(values).__name__}")
        return values
