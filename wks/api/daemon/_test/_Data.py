"""Test backend daemon configuration."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Data(BaseModel):
    """Minimal daemon config used for tests."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., description="Identifier for the test daemon")
    log_file: str = Field(..., description="Relative log path")
    keep_alive: bool = Field(..., description="Keep-alive flag")
    run_at_load: bool = Field(..., description="Run at load flag")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if not v:
            raise ValueError("label is required for test daemon backend")
        return v

    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, v: str) -> str:
        path = Path(v)
        if path.is_absolute():
            raise ValueError("log_file must be relative for test daemon backend")
        return v
