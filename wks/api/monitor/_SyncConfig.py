"""Sync configuration."""

from pydantic import BaseModel, Field, field_validator


class _SyncConfig(BaseModel):
    """Sync configuration."""

    database: str = Field(..., description="Database name in 'database.collection' format")
    max_documents: int = Field(1000000, ge=0)
    min_priority: float = Field(0.0, ge=0.0)
    prune_interval_secs: float = Field(300.0, gt=0)

    @field_validator("database")
    @classmethod
    def validate_database_format(cls, v: str) -> str:
        """Validate database string is in 'database.collection' format."""
        if "." not in v:
            raise ValueError("Database must be in format 'database.collection' (e.g., 'wks.monitor')")
        parts = v.split(".", 1)
        if not parts[0] or not parts[1]:
            raise ValueError("Database must be in format 'database.collection' with both parts non-empty")
        return v

