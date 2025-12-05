"""Filter configuration."""

from pydantic import BaseModel, Field


class _FilterConfig(BaseModel):
    """Filter configuration for monitor paths."""

    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    include_dirnames: list[str] = Field(default_factory=list)
    exclude_dirnames: list[str] = Field(default_factory=list)
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)

