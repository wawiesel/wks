"""Monitor status and validation result models.

This module contains Pydantic models for monitor status, validation results,
and operation results.
"""

from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class ListOperationResult(BaseModel):
    """Result of adding/removing items from a monitor list."""

    success: bool
    message: str = Field(..., min_length=1)
    value_stored: str | None = None
    value_removed: str | None = None
    not_found: bool = False
    already_exists: bool = False
    validation_failed: bool = False

    @field_validator("message")
    @classmethod
    def message_cannot_be_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("message cannot be empty")
        return v

    @field_validator("not_found", "already_exists", "validation_failed")
    @classmethod
    def check_success_status(cls, v: bool, info: ValidationInfo) -> bool:
        values = info.data
        if values.get("success") and v:
            raise ValueError(f"success cannot be True when {info.field_name} is True")
        return v


class ManagedDirectoryInfo(BaseModel):
    """Information about a managed directory."""

    priority: int = Field(..., ge=0)
    valid: bool
    error: str | None = None


class ManagedDirectoriesResult(BaseModel):
    """Result of get_managed_directories()."""

    managed_directories: dict[str, int]
    count: int
    validation: dict[str, ManagedDirectoryInfo]


class ConfigValidationResult(BaseModel):
    """Result of validate_config()."""

    issues: list[str] = Field(default_factory=list)
    redundancies: list[str] = Field(default_factory=list)
    managed_directories: dict[str, ManagedDirectoryInfo] = Field(default_factory=dict)
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


ConfigValidationResult.model_rebuild()


class MonitorStatus(BaseModel):
    """Monitor status data structure."""

    tracked_files: int = Field(..., ge=0)
    issues: list[str] = Field(default_factory=list)
    redundancies: list[str] = Field(default_factory=list)
    managed_directories: dict[str, ManagedDirectoryInfo] = Field(default_factory=dict)
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
