"""Shared service-layer models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

FailureKind = Literal["config", "validation", "not_found", "conflict", "runtime"]


class ServiceResponse(BaseModel):
    """Common envelope for service-layer responses."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    failure_kind: FailureKind | None = None
