"""Sync result model."""

from dataclasses import dataclass

from ._constants import DOC_TYPE_META, META_DOCUMENT_ID
from .ScanStats import ScanStats


@dataclass
class SyncResult:
    stats: ScanStats
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
            "links_written": self.stats.edge_total,
            "type_counts": dict(self.stats.type_counts),
            "status_counts": dict(self.stats.status_counts),
            "errors": list(self.stats.errors),
        }
