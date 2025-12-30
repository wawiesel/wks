"""Log configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LogConfig(BaseModel):
    """Log retention configuration."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["DEBUG", "INFO", "WARN", "ERROR"] = Field(..., description="Logging level")
    debug_retention_days: float = Field(..., gt=0, description="Days to retain debug entries in log")
    info_retention_days: float = Field(..., gt=0, description="Days to retain info entries in log")
    warning_retention_days: float = Field(..., gt=0, description="Days to retain warnings in log")
    error_retention_days: float = Field(..., gt=0, description="Days to retain errors in log")
