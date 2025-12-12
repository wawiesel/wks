"""Filter configuration."""

from pydantic import BaseModel, Field


class _FilterConfig(BaseModel):
    """Filter configuration for monitor paths."""

    include_paths: list[str] = Field(...)
    exclude_paths: list[str] = Field(...)
    include_dirnames: list[str] = Field(...)
    exclude_dirnames: list[str] = Field(...)
    include_globs: list[str] = Field(...)
    exclude_globs: list[str] = Field(...)
