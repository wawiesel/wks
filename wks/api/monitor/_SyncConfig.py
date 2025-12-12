"""Sync configuration."""

from pydantic import BaseModel, Field


class _SyncConfig(BaseModel):
    """Sync configuration."""

    max_documents: int = Field(..., ge=0)
    min_priority: float = Field(..., ge=0.0)
    prune_interval_secs: float = Field(..., gt=0)
