"""Diff result dataclass."""

from dataclasses import dataclass
from typing import Any

from .BinaryDiffOutput import BinaryDiffOutput
from .CodeDiffOutput import CodeDiffOutput
from .DiffMetadata import DiffMetadata
from .TextDiffOutput import TextDiffOutput


@dataclass(frozen=True)
class DiffResult:
    """Result of a diff operation."""

    status: str
    metadata: DiffMetadata
    diff_output: TextDiffOutput | BinaryDiffOutput | CodeDiffOutput | None = None
    message: str | None = None
    error_details: dict[str, Any] | None = None
