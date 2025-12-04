from typing import Any, List, Optional, Dict

from pydantic import BaseModel, Field, ValidationError, field_validator


class ListOperationResult(BaseModel):
    """Result of adding/removing items from a monitor list."""

    success: bool
    message: str = Field(..., min_length=1)
    value_stored: Optional[str] = None
    value_removed: Optional[str] = None
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
    def check_success_status(cls, v: bool, info: field_validator) -> bool:
        values = info.data
        if values.get("success") and v:
            raise ValueError(f"success cannot be True when {info.field_name} is True")
        return v


class ManagedDirectoryInfo(BaseModel):
    """Information about a managed directory."""

    priority: int = Field(..., ge=0)
    valid: bool
    error: Optional[str] = None


class ManagedDirectoriesResult(BaseModel):
    """Result of get_managed_directories()."""

    managed_directories: dict[str, int]
    count: int
    validation: dict[str, ManagedDirectoryInfo]


class ConfigValidationResult(BaseModel):
    """Result of validate_config()."""

    issues: List[str] = Field(default_factory=list)
    redundancies: List[str] = Field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = Field(default_factory=dict)
    include_paths: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(default_factory=list)
    include_dirnames: List[str] = Field(default_factory=list)
    exclude_dirnames: List[str] = Field(default_factory=list)
    include_globs: List[str] = Field(default_factory=list)
    exclude_globs: List[str] = Field(default_factory=list)
    include_dirname_validation: Dict[str, Any] = Field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Any] = Field(default_factory=dict)
    include_glob_validation: Dict[str, Any] = Field(default_factory=dict)
    exclude_glob_validation: Dict[str, Any] = Field(default_factory=dict)


ConfigValidationResult.model_rebuild()


class MonitorStatus(BaseModel):
    """Monitor status data structure."""

    tracked_files: int = Field(..., ge=0)
    issues: List[str] = Field(default_factory=list)
    redundancies: List[str] = Field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = Field(default_factory=dict)
    include_paths: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(default_factory=list)
    include_dirnames: List[str] = Field(default_factory=list)
    exclude_dirnames: List[str] = Field(default_factory=list)
    include_globs: List[str] = Field(default_factory=list)
    exclude_globs: List[str] = Field(default_factory=list)
    include_dirname_validation: Dict[str, Any] = Field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Any] = Field(default_factory=dict)
    include_glob_validation: Dict[str, Any] = Field(default_factory=dict)
    exclude_glob_validation: Dict[str, Any] = Field(default_factory=dict)
