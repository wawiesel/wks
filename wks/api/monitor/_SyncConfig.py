"""Sync configuration."""

from pydantic import BaseModel, Field, field_validator


class _SyncConfig(BaseModel):
    """Sync configuration."""

    max_documents: int = Field(1000000, ge=0)
    min_priority: float = Field(0.0, ge=0.0)
    prune_interval_secs: float = Field(300.0, gt=0)

