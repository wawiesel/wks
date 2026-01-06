"""Diff metadata dataclass."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DiffMetadata:
    """Metadata describing a diff operation."""

    engine_used: str
    is_identical: bool
    file_type_a: str | None = None
    file_type_b: str | None = None
    checksum_a: str | None = None
    checksum_b: str | None = None
    encoding_a: str | None = None
    encoding_b: str | None = None
