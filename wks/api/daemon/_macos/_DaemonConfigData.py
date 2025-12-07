"""macOS (launchd) specific daemon configuration data."""

from pydantic import BaseModel, Field, field_validator


class _DaemonConfigData(BaseModel):
    """macOS launchd daemon configuration data."""

    label: str = Field(..., description="Launchd service identifier (reverse DNS format)")
    working_directory: str = Field(..., description="Directory where daemon runs")
    log_file: str = Field(..., description="Path to standard output log file")
    error_log_file: str = Field(..., description="Path to standard error log file")
    keep_alive: bool = Field(..., description="Whether launchd should auto-restart daemon if it exits")
    run_at_load: bool = Field(..., description="Whether service should start automatically when installed")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        if not v:
            raise ValueError("daemon.data.label is required when daemon.type is 'macos'")
        # Basic reverse DNS format validation
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError(f"daemon.data.label must be in reverse DNS format (e.g., 'com.example.app'), got: {v!r}")
        return v

