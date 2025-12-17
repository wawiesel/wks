"""Vault data structures (private)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .._constants import DOC_TYPE_LINK, DOC_TYPE_META, META_DOCUMENT_ID


def _identity(note_path: str, line_number: int, column_number: int, target_uri: str) -> str:
    payload = f"{note_path}|{line_number}|{column_number}|{target_uri}".encode("utf-8", errors="ignore")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class _EdgeRecord:
    """Single vault edge with URI-first schema."""

    # Source context
    note_path: str
    from_uri: str
    line_number: int
    column_number: int
    source_heading: str
    raw_line: str

    # Link content
    link_type: str
    raw_target: str
    alias_or_text: str

    # Target resolution (URI-first)
    to_uri: str
    status: str

    @property
    def identity(self) -> str:
        return _identity(self.note_path, self.line_number, self.column_number, self.to_uri)

    def to_document(self, seen_at_iso: str) -> dict[str, object]:
        return {
            "_id": self.identity,
            "doc_type": DOC_TYPE_LINK,
            "from_uri": self.from_uri,
            "to_uri": self.to_uri,
            "line_number": self.line_number,
            "column_number": self.column_number,
            "source_heading": self.source_heading,
            "raw_line": self.raw_line,
            "link_type": self.link_type,
            "raw_target": self.raw_target,
            "alias_or_text": self.alias_or_text,
            "status": self.status,
            "last_seen": seen_at_iso,
            "last_updated": seen_at_iso,
        }


@dataclass
class _ScanStats:
    notes_scanned: int
    edge_total: int
    type_counts: dict[str, int]
    status_counts: dict[str, int]
    errors: list[str]
    scanned_files: set[str] = field(default_factory=set)


@dataclass
class _SyncResult:
    stats: _ScanStats
    sync_started: str
    sync_duration_ms: int
    deleted_records: int
    upserts: int

    def to_meta_document(self) -> dict[str, object]:
        return {
            "_id": META_DOCUMENT_ID,
            "doc_type": DOC_TYPE_META,
            "last_scan_started_at": self.sync_started,
            "last_scan_duration_ms": self.sync_duration_ms,
            "notes_scanned": self.stats.notes_scanned,
            "edges_written": self.stats.edge_total,
            "type_counts": dict(self.stats.type_counts),
            "status_counts": dict(self.stats.status_counts),
            "errors": list(self.stats.errors),
        }
