"""Output schemas for database commands."""

from typing import Any

from pydantic import Field

from ._base import BaseOutputSchema
from ._registry import register_output_schema


class DatabaseListOutput(BaseOutputSchema):
    """Output schema for database list command."""
    databases: list[str] = Field(..., description="List of database names")


class DatabaseShowOutput(BaseOutputSchema):
    """Output schema for database show command."""
    database: str = Field(..., description="Database/collection name")
    query: dict[str, Any] = Field(..., description="Query filter (JSON parsed), empty dict if no filter")
    limit: int = Field(..., description="Result limit")
    count: int = Field(..., description="Number of documents found")
    results: list[dict[str, Any]] = Field(..., description="Query results")


class DatabaseResetOutput(BaseOutputSchema):
    """Output schema for database reset command."""
    database: str = Field(..., description="Database name")
    deleted_count: int = Field(..., description="Number of documents deleted, -1 if not applicable")


# Register all schemas
register_output_schema("database", "list", DatabaseListOutput)
register_output_schema("database", "show", DatabaseShowOutput)
register_output_schema("database", "reset", DatabaseResetOutput)
