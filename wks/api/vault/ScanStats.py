"""Scan stats model."""

from dataclasses import dataclass, field


@dataclass
class ScanStats:
    notes_scanned: int
    edge_total: int
    type_counts: dict[str, int]
    status_counts: dict[str, int]
    errors: list[str]
    scanned_files: set[str] = field(default_factory=set)
