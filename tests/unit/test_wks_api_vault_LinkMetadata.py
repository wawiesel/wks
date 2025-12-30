from wks.api.vault.LinkMetadata import LinkMetadata


def test_link_metadata_to_dict():
    """Test to_dict method (line 19)."""
    meta = LinkMetadata(target_uri="vault:///test.md", status="ok")
    d = meta.to_dict()
    assert d == {"target_uri": "vault:///test.md", "status": "ok"}
