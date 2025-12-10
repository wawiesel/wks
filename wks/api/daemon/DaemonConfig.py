"""Daemon configuration (simple, no optional fields)."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    sync_interval_secs: float = Field(..., gt=0, description="Interval to poll/flush filesystem events")
    log_file: str = Field(..., description="Relative log file path (under WKS_HOME)")
    restrict_dir: str = Field(
        ...,
        description="Directory root to watch; use empty string to fall back to monitor include paths",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            raise ValueError(f"daemon config must be a dict, got {type(values).__name__}")

        log_file = values.get("log_file")
        if not log_file:
            raise ValueError("daemon.log_file is required")
        from pathlib import PurePath

        p = PurePath(log_file)
        if p.is_absolute():
            raise ValueError("daemon.log_file must be relative to WKS_HOME")

        if "restrict_dir" not in values:
            raise ValueError("daemon.restrict_dir is required (use empty string to watch all configured paths)")

        return values
