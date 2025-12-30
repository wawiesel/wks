"""Unit tests for wks.api.vault.SyncResult."""

from wks.api.vault.ScanStats import ScanStats
from wks.api.vault.SyncResult import SyncResult


def test_sync_result_to_meta_document():
    """Test converting SyncResult to meta document."""
    stats = ScanStats(
        notes_scanned=10,
        edge_total=5,
        type_counts={"wikilink": 3, "url": 2},
        status_counts={"ok": 4, "broken": 1},
        errors=[],
    )

    result = SyncResult(
        stats=stats,
        sync_started="2025-01-01T00:00:00Z",
        sync_duration_ms=100,
        deleted_records=1,
        upserts=2,
    )

    doc = result.to_meta_document()

    assert doc["_id"] == "__meta__"
    assert doc["doc_type"] == "meta"
    assert doc["last_scan_started_at"] == "2025-01-01T00:00:00Z"
    assert doc["notes_scanned"] == 10
    assert doc["links_written"] == 5
