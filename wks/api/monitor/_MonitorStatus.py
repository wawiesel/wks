"""Monitor status model."""

from typing import Any

from pydantic import BaseModel, Field

from ._PriorityDirectoryInfo import _PriorityDirectoryInfo


class _MonitorStatus(BaseModel):
    """Monitor status data structure."""

    tracked_files: int = Field(..., ge=0)
    issues: list[str] = Field(default_factory=list)
    redundancies: list[str] = Field(default_factory=list)
    managed_directories: dict[str, _PriorityDirectoryInfo] = Field(default_factory=dict)
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    include_dirnames: list[str] = Field(default_factory=list)
    exclude_dirnames: list[str] = Field(default_factory=list)
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)
    include_dirname_validation: dict[str, Any] = Field(default_factory=dict)
    exclude_dirname_validation: dict[str, Any] = Field(default_factory=dict)
    include_glob_validation: dict[str, Any] = Field(default_factory=dict)
    exclude_glob_validation: dict[str, Any] = Field(default_factory=dict)

