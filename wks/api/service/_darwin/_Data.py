"""macOS (launchd) specific daemon configuration data."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, ConfigDict


class _Data(BaseModel):
    """macOS launchd daemon configuration data."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Launchd service identifier (reverse DNS format)")
    keep_alive: bool = Field(..., description="Whether launchd should auto-restart daemon if it exits")
    run_at_load: bool = Field(..., description="Whether service should start automatically when installed")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if not v:
            raise ValueError("daemon.data.label is required when daemon.type is 'darwin'")
        # Basic reverse DNS format validation
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError(f"daemon.data.label must be in reverse DNS format (e.g., 'com.example.app'), got: {v!r}")
        return v

