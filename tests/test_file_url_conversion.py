"""Test automatic conversion of file:// URLs to _links/ symlinks."""

from pathlib import Path
import platform
import mongomock
import pytest

from wks.vault.obsidian import ObsidianVault
from wks.vault.indexer import VaultLinkIndexer, VaultLinkScanner
from wks.vault.config import VaultDatabaseConfig


@pytest.fixture()
def test_setup(tmp_path, monkeypatch):
    """Set up vault and external file."""
    # Create vault
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    (vault_root / "_links").mkdir()
    (vault_root / "Projects").mkdir()

    # Create external file
    external_file = tmp_path / "docs" / "paper.pdf"
    external_file.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("PDF content")

    # Create note with file:// URL
    note = vault_root / "Projects" / "Research.md"
    file_url = external_file.as_uri()
    note.write_text(f"Reference: [PDF Document]({file_url})")

    # Patch MongoDB
    client = mongomock.MongoClient()
    monkeypatch.setattr("wks.vault.indexer.MongoClient", lambda *a, **k: client)
    from mongomock.collection import BulkOperationBuilder
    original = BulkOperationBuilder.add_update
    def wrapper(self, selector, document, check_keys, upsert, **kwargs):
        return original(self, selector, document, check_keys, upsert)
    monkeypatch.setattr(BulkOperationBuilder, "add_update", wrapper)

    return {
        "vault_root": vault_root,
        "external_file": external_file,
        "note": note,
        "file_url": file_url,
        "mongo_client": client,
    }


def test_file_url_auto_conversion(test_setup):
    """Test that file:// URLs are automatically converted to [[_links/...]] wikilinks."""
    vault_root = test_setup["vault_root"]
    external_file = test_setup["external_file"]
    note = test_setup["note"]
    file_url = test_setup["file_url"]
    mongo_client = test_setup["mongo_client"]

    # Get machine name
    machine = platform.node().split(".")[0]

    # Setup vault and scanner
    vault = ObsidianVault(vault_path=vault_root, base_dir="Projects")
    scanner = VaultLinkScanner(vault)

    print(f"\n✓ Initial note content:")
    print(f"  {note.read_text()}")
    print(f"  File URL: {file_url}")

    # Scan - should detect file:// URL, create symlink, and rewrite markdown
    records = scanner.scan()

    # Verify symlink was created
    expected_symlink = vault_root / "_links" / machine / str(external_file).lstrip("/")
    assert expected_symlink.exists(), f"Symlink not created at {expected_symlink}"
    assert expected_symlink.is_symlink(), "Path exists but is not a symlink"
    print(f"✓ Symlink created: {expected_symlink}")

    # Verify symlink points to external file
    resolved = expected_symlink.resolve()
    assert resolved == external_file, f"Symlink points to {resolved}, expected {external_file}"
    print(f"✓ Symlink points to: {external_file}")

    # Verify markdown was rewritten
    new_content = note.read_text()
    assert "[PDF Document](" + file_url + ")" not in new_content, "Old file:// URL still in markdown"
    expected_link = f"[[_links/{machine}/{str(external_file).lstrip('/')}]]"
    assert expected_link in new_content, f"Expected wikilink not found in markdown: {expected_link}"
    print(f"✓ Markdown rewritten to: {new_content}")

    # Verify record was created with correct type (wikilink, not markdown_url)
    assert len(records) == 1
    record = records[0]
    assert record.link_type == "wikilink", f"Expected wikilink, got {record.link_type}"
    assert record.to_uri.startswith("file://"), f"Expected file:// URI, got {record.to_uri}"
    print(f"✓ Record created with link_type={record.link_type}, to_uri={record.to_uri}")


def test_file_url_with_indexer(test_setup):
    """Test full indexing pipeline with file:// URL conversion."""
    vault_root = test_setup["vault_root"]
    external_file = test_setup["external_file"]
    note = test_setup["note"]
    file_url = test_setup["file_url"]
    mongo_client = test_setup["mongo_client"]

    # Setup vault and indexer
    vault = ObsidianVault(vault_path=vault_root, base_dir="Projects")
    cfg = {"vault": {"database": "wks.vault"}, "db": {"uri": "mongodb://localhost:27017/"}}
    db_config = VaultDatabaseConfig.from_config(cfg)
    indexer = VaultLinkIndexer(vault, db_config=db_config)

    print(f"\n✓ Original markdown: {note.read_text()}")

    # Sync - should convert file:// URL and index
    result = indexer.sync()
    assert result.stats.edge_total == 1
    print(f"✓ Indexed {result.stats.edge_total} link(s)")

    # Verify markdown was rewritten
    new_content = note.read_text()
    assert file_url not in new_content
    machine = platform.node().split(".")[0]
    expected_link = f"[[_links/{machine}/{str(external_file).lstrip('/')}]]"
    assert expected_link in new_content
    print(f"✓ Markdown rewritten: {new_content}")

    # Verify database
    collection = mongo_client["wks"]["vault"]
    link_doc = collection.find_one({"doc_type": "link"})
    assert link_doc is not None
    assert link_doc["link_type"] == "wikilink"
    assert link_doc["to_uri"].startswith("file://")
    print(f"✓ Database indexed with:")
    print(f"  link_type: {link_doc['link_type']}")
    print(f"  to: {link_doc['to']}")
    print(f"  to_uri: {link_doc['to_uri']}")


def test_nonexistent_file_url(test_setup):
    """Test that file:// URLs pointing to nonexistent files are handled gracefully."""
    vault_root = test_setup["vault_root"]
    note = test_setup["note"]

    # Write link to nonexistent file
    note.write_text("[Bad Link](file:///nonexistent/file.pdf)")

    vault = ObsidianVault(vault_path=vault_root, base_dir="Projects")
    scanner = VaultLinkScanner(vault)

    # Scan - should not crash
    records = scanner.scan()

    # Should have error logged
    assert len(scanner.stats.errors) > 0
    assert any("non-existent" in err for err in scanner.stats.errors)
    print(f"✓ Error logged: {scanner.stats.errors[0]}")

    # Markdown should not be rewritten
    content = note.read_text()
    assert "file:///nonexistent/file.pdf" in content
    print("✓ Markdown unchanged for nonexistent file")
