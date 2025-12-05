"""List operation result model."""

from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class _ListOperationResult(BaseModel):
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

