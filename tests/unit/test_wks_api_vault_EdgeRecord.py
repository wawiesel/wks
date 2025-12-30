"""Tests for EdgeRecord."""

from wks.api.vault.EdgeRecord import EdgeRecord


def test_edge_record_identity_consistency():
    """Test that EdgeRecord identity is deterministic and correct."""
    edge1 = EdgeRecord(
        note_path="note.md",
        from_uri="vault:///note.md",
        line_number=10,
        column_number=5,
        source_heading="H1",
        raw_line="[[target]]",
        link_type="wikilink",
        raw_target="target",
        alias_or_text="",
        to_uri="vault:///target.md",
        status="ok",
    )
    edge2 = EdgeRecord(
        note_path="note.md",
        from_uri="vault:///note.md",
        line_number=10,
        column_number=5,
        source_heading="H1",
        raw_line="[[target]]",
        link_type="wikilink",
        raw_target="target",
        alias_or_text="",
        to_uri="vault:///target.md",
        status="ok",
    )
    assert edge1.identity == edge2.identity

    # Change one field that affects identity
    edge3 = EdgeRecord(
        note_path="note.md",
        from_uri="vault:///note.md",
        line_number=10,
        column_number=6,
        source_heading="H1",
        raw_line=" [[target]]",
        link_type="wikilink",
        raw_target="target",
        alias_or_text="",
        to_uri="vault:///target.md",
        status="ok",
    )
    assert edge1.identity != edge3.identity


def test_edge_record_to_document():
    """Test conversion to database document."""
    edge = EdgeRecord(
        note_path="Note 📝.md",
        from_uri="vault:///note.md",
        line_number=1,
        column_number=1,
        source_heading="",
        raw_line="[[target]]",
        link_type="wikilink",
        raw_target="target",
        alias_or_text="",
        to_uri="vault:///target.md",
        status="ok",
    )
    doc = edge.to_document("2025-01-01T00:00:00Z")
    assert doc["_id"] == edge.identity
    assert doc["last_seen"] == "2025-01-01T00:00:00Z"
