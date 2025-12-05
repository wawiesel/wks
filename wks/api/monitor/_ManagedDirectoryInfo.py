"""Priority directory info model."""

from pydantic import BaseModel, Field


class _ManagedDirectoryInfo(BaseModel):
    """Information about a priority directory."""

    priority: float = Field(..., ge=0)
    valid: bool
    error: str | None = None

