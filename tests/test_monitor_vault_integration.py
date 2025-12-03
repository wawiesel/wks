"""Integration test for monitor-vault sync on file moves."""

import mongomock
import pytest

from wks.vault.indexer import VaultLinkIndexer
from wks.vault.obsidian import ObsidianVault


@pytest.fixture()
def test_env(tmp_path, monkeypatch):
    """Set up test environment with vault and external file."""
    # Create vault
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    (vault_root / "_links").mkdir()
    (vault_root / "WKS").mkdir()
    (vault_root / "Projects").mkdir()

    # Create external file
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_file = external_dir / "paper.pdf"
    external_file.write_text("PDF content")

    # Create symlink to external file
    symlink = vault_root / "_links" / "mbp-2021" / "external" / "paper.pdf"
    symlink.parent.mkdir(parents=True, exist_ok=True)
    symlink.symlink_to(external_file)

    # Create note linking to external file
    note = vault_root / "Projects" / "Research.md"
    note.write_text("See [[_links/mbp-2021/external/paper.pdf]] for details.")

    # Patch MongoDB
    client = mongomock.MongoClient()
    monkeypatch.setattr("wks.vault.indexer.MongoClient", lambda *a, **k: client)

    # Mock BulkOperationBuilder.add_update signature fix
    from mongomock.collection import BulkOperationBuilder

    original = BulkOperationBuilder.add_update

    def wrapper(self, selector, document, check_keys, upsert, **kwargs):
        return original(self, selector, document, check_keys, upsert)

    monkeypatch.setattr(BulkOperationBuilder, "add_update", wrapper)

    return {
        "vault_root": vault_root,
        "external_file": external_file,
        "external_dir": external_dir,
        "symlink": symlink,
        "note": note,
        "mongo_client": client,
    }


def test_monitor_vault_sync_on_file_move(test_env):
    """Test that moving a file updates vault DB with new URI."""
    vault_root = test_env["vault_root"]
    external_file = test_env["external_file"]
    external_dir = test_env["external_dir"]
    mongo_client = test_env["mongo_client"]

    # Setup vault and indexer
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    indexer = VaultLinkIndexer(vault=vault, mongo_uri="mongodb://localhost:27017", db_name="wks", coll_name="vault")

    # Initial sync - index the link
    result = indexer.sync()
    assert result.stats.edge_total == 1

    # Verify initial state
    collection = mongo_client["wks"]["vault"]
    link_doc = collection.find_one({"doc_type": "link"})
    assert link_doc is not None
    assert link_doc["from_uri"] == "vault:///Projects/Research.md"
    old_uri = link_doc["to_uri"]
    assert old_uri == external_file.as_uri()
    print(f"✓ Initial link indexed with URI: {old_uri}")

    # Simulate file move
    new_location = external_dir / "archive" / "paper.pdf"
    new_location.parent.mkdir(parents=True, exist_ok=True)
    external_file.rename(new_location)

    old_uri_str = external_file.as_uri()
    new_uri_str = new_location.as_uri()
    print(f"✓ File moved: {external_file} → {new_location}")
    print(f"  Old URI: {old_uri_str}")
    print(f"  New URI: {new_uri_str}")

    # Call the update method (simulating daemon's move handler)
    updated_count = indexer.update_links_on_file_move(old_uri_str, new_uri_str)
    assert updated_count == 1
    print(f"✓ Updated {updated_count} vault link(s)")

    # Verify vault DB was updated
    updated_doc = collection.find_one({"doc_type": "link"})
    assert updated_doc is not None
    assert updated_doc["from_uri"] == "vault:///Projects/Research.md"
    assert updated_doc["to_uri"] == new_uri_str  # to_uri updated!
    assert updated_doc["status"] == "ok"
    print(f"✓ Vault DB updated with new URI: {updated_doc['to_uri']}")

    # Verify old URI no longer in DB
    old_links = list(collection.find({"to_uri": old_uri_str}))
    assert len(old_links) == 0
    print("✓ Old URI no longer in database")

    # Verify new URI is in DB
    new_links = list(collection.find({"to_uri": new_uri_str}))
    assert len(new_links) == 1
    print("✓ New URI found in database")


def test_multiple_links_to_same_file(test_env):
    """Test that moving a file updates ALL links pointing to it."""
    vault_root = test_env["vault_root"]
    external_file = test_env["external_file"]
    external_dir = test_env["external_dir"]
    mongo_client = test_env["mongo_client"]

    # Create multiple notes linking to same file
    note1 = vault_root / "Projects" / "Note1.md"
    note1.write_text("Reference: [[_links/mbp-2021/external/paper.pdf]]")

    note2 = vault_root / "Projects" / "Note2.md"
    note2.write_text("See also: [[_links/mbp-2021/external/paper.pdf|Paper]]")

    note3 = vault_root / "WKS" / "Note3.md"
    note3.write_text("Embed: ![[_links/mbp-2021/external/paper.pdf]]")

    # Setup and sync
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    indexer = VaultLinkIndexer(vault=vault, mongo_uri="mongodb://localhost:27017", db_name="wks", coll_name="vault")

    result = indexer.sync()
    # Original link from Research.md + 3 new links = 4 total
    assert result.stats.edge_total == 4
    print(f"✓ Indexed {result.stats.edge_total} links to same file")

    # Move file
    new_location = external_dir / "moved" / "paper.pdf"
    new_location.parent.mkdir(parents=True, exist_ok=True)
    external_file.rename(new_location)

    old_uri = external_file.as_uri()
    new_uri = new_location.as_uri()

    # Update vault DB
    updated_count = indexer.update_links_on_file_move(old_uri, new_uri)
    assert updated_count == 4
    print(f"✓ Updated all {updated_count} links to new URI")

    # Verify all links updated
    collection = mongo_client["wks"]["vault"]
    all_links = list(collection.find({"to_uri": new_uri}))
    assert len(all_links) == 4

    # Verify each link has correct to_uri
    for link in all_links:
        assert link["to_uri"] == new_uri
        assert link["status"] == "ok"

    print("✓ All links verified with new URI")
