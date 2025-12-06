from pathlib import Path
from unittest.mock import Mock, patch

import mongomock
import pytest
from wks.api.db._mongo.MongoDbConfig import MongoDbConfig
from wks.config import VaultConfig, WKSConfig

from wks.vault.constants import (
    LINK_TYPE_EMBED,
    LINK_TYPE_MARKDOWN_URL,
    LINK_TYPE_WIKILINK,
    STATUS_LEGACY_LINK,
    STATUS_MISSING_SYMLINK,
    STATUS_OK,
)
from wks.vault.indexer import VaultLinkIndexer
from wks.vault.link_resolver import LinkResolver
from wks.vault.obsidian import ObsidianVault
from wks.vault.status_controller import VaultStatusController


@pytest.fixture()
def vault_root(tmp_path: Path):
    root = tmp_path / "vault"
    (root / "_links").mkdir(parents=True, exist_ok=True)
    (root / "WKS").mkdir(exist_ok=True)
    (root / "Projects").mkdir(exist_ok=True)
    real_file = tmp_path / "paper.pdf"
    real_file.write_text("content")
    symlink = root / "_links" / "papers" / "paper.pdf"
    symlink.parent.mkdir(parents=True, exist_ok=True)
    symlink.symlink_to(real_file)
    note = root / "Projects" / "Demo.md"
    note.write_text("See [[_links/papers/paper.pdf]]\n\n[Docs](https://example.com)")
    return root


@pytest.fixture()
def vault(vault_root):
    return ObsidianVault(
        vault_path=vault_root,
        base_dir="WKS",
    )


@pytest.fixture()
def patched_mongo(monkeypatch):
    client: mongomock.MongoClient = mongomock.MongoClient()
    monkeypatch.setattr("wks.vault.indexer.MongoClient", lambda *a, **k: client)  # noqa: ARG005
    monkeypatch.setattr("wks.vault.status_controller.MongoClient", lambda *a, **k: client)  # noqa: ARG005
    from mongomock.collection import BulkOperationBuilder

    original = BulkOperationBuilder.add_update

    def wrapper(self, selector, document, check_keys, upsert, **kwargs):  # noqa: ARG001
        return original(self, selector, document, check_keys, upsert)

    monkeypatch.setattr(BulkOperationBuilder, "add_update", wrapper)
    return client


def test_vault_link_indexer_and_status(vault, vault_root, patched_mongo):
    indexer = VaultLinkIndexer(
        vault=vault,
        mongo_uri="mongodb://localhost:27017",
        db_name="test_wks",
        coll_name="test_vault",
    )
    result = indexer.sync()
    assert result.stats.edge_total == 2
    mongo_coll = patched_mongo["test_wks"]["test_vault"]
    edge = mongo_coll.find_one({"doc_type": "link", "link_type": LINK_TYPE_WIKILINK})
    assert edge["from_uri"] == "vault:///Projects/Demo.md"
    assert edge["raw_target"] == "_links/papers/paper.pdf"
    assert edge["to_uri"].startswith("file:///")  # Resolved filesystem URI
    assert "from" not in edge
    assert "to" not in edge
    assert edge["status"] == STATUS_OK
    # Removed fields should not exist
    assert "links_rel" not in edge
    assert "resolved_path" not in edge
    assert "resolved_exists" not in edge
    assert "is_embed" not in edge
    assert "target_kind" not in edge
    # Patch WKSConfig to match the test DB settings
    mock_config = Mock(spec=WKSConfig)
    mock_config.vault = Mock(spec=VaultConfig)
    mock_config.vault.database = "test_wks.test_vault"
    mock_config.db = Mock(spec=MongoDbConfig)
    mock_config.db.uri = "mongodb://localhost:27017"

    with patch("wks.config.WKSConfig.load", return_value=mock_config):
        summary = VaultStatusController().summarize()
        assert summary.total_links == 2
        assert summary.external_urls == 1
        symlink = vault_root / "_links" / "papers" / "paper.pdf"
        symlink.unlink()
        indexer.sync()
        summary = VaultStatusController().summarize()
        assert summary.missing_symlink >= 1
        assert summary.issues


def test_legacy_links_detection(vault_root):
    """Test legacy links/ path detection and status."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    resolver = LinkResolver(vault.links_dir)

    result = resolver.resolve("links/old/document.pdf")
    assert result.status == STATUS_LEGACY_LINK
    assert "legacy:///" in result.target_uri


def test_wikilink_alias_parsing():
    """Test [[target|alias]] parsing edge cases."""
    vault_root = Path("/tmp/test_vault")
    resolver = LinkResolver(vault_root / "_links")

    # Standard alias
    result = resolver.resolve("SomeNote|Display Text")
    assert result.status == STATUS_OK

    # Empty alias (after split, not handled by resolver)
    result = resolver.resolve("SomeNote")
    assert result.status == STATUS_OK


def test_external_url_extraction(vault_root):
    """Test external URL detection."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    resolver = LinkResolver(vault.links_dir)

    result = resolver.resolve("https://example.com/page")
    assert result.status == STATUS_OK
    assert result.target_uri == "https://example.com/page"


def test_attachment_detection(vault_root):
    """Test vault attachment (_prefix) detection."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    resolver = LinkResolver(vault.links_dir)

    result = resolver.resolve("_attachments/image.png")
    assert result.status == STATUS_OK
    assert result.target_uri == "vault:///_attachments/image.png"


def test_symlink_missing_target(vault_root):
    """Test broken symlink is detected as missing_symlink."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")

    # Create a broken symlink (target doesn't exist)
    symlink_path = vault.links_dir / "broken" / "link.pdf"
    symlink_path.parent.mkdir(parents=True, exist_ok=True)
    symlink_path.symlink_to("/nonexistent/file.pdf")

    resolver = LinkResolver(vault.links_dir)
    result = resolver.resolve("_links/broken/link.pdf")

    # Broken symlinks are detected as missing_symlink since .exists() is False
    assert result.status == STATUS_MISSING_SYMLINK


def test_scanner_error_handling(vault_root, tmp_path):  # noqa: ARG001
    """Test scanner continues on individual file errors."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")

    # Create a valid note
    note1 = vault_root / "Projects" / "Good.md"
    note1.write_text("[[ValidLink]]")

    # Create an unreadable note (simulate by using a directory)
    bad_note_dir = vault_root / "Projects" / "Bad.md"
    bad_note_dir.mkdir(exist_ok=True)

    from wks.vault.indexer import VaultLinkScanner

    scanner = VaultLinkScanner(vault)
    scanner.scan()

    # Should have scanned the good note despite bad one
    assert scanner.stats.notes_scanned >= 1
    assert len(scanner.stats.errors) >= 1


def test_embed_vs_wikilink_distinction(vault_root):
    """Test that embeds (![[...]]) are distinguished from regular wikilinks."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    note = vault_root / "Projects" / "Test.md"
    note.write_text("Regular: [[Link1]]\nEmbed: ![[Link2]]")

    from wks.vault.indexer import VaultLinkScanner

    scanner = VaultLinkScanner(vault)
    records = scanner.scan()

    # Find the two records
    link_types = [r.link_type for r in records if r.note_path == "Projects/Test.md"]
    assert LINK_TYPE_WIKILINK in link_types
    assert LINK_TYPE_EMBED in link_types


def test_markdown_url_extraction(vault_root):
    """Test markdown [text](url) pattern matching."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    note = vault_root / "Projects" / "URLs.md"
    note.write_text("[GitHub](https://github.com)\n[Docs](https://docs.example.com/page)")

    from wks.vault.indexer import VaultLinkScanner

    scanner = VaultLinkScanner(vault)
    records = scanner.scan()

    urls = [r.to_uri for r in records if r.link_type == LINK_TYPE_MARKDOWN_URL]
    assert "https://github.com" in urls
    assert "https://docs.example.com/page" in urls


def test_batch_processing(vault, vault_root, patched_mongo):  # noqa: ARG001
    """Test batch processing with small batch size."""
    indexer = VaultLinkIndexer(
        vault=vault,
        mongo_uri="mongodb://localhost:27017",
        db_name="test_wks",
        coll_name="test_vault",
    )
    result = indexer.sync(batch_size=10)

    # Should have processed all records
    assert result.stats.edge_total == 2

    # This test is no longer relevant as VaultDatabaseConfig is removed
    pass


def test_line_preview_truncation(vault_root):
    """Test that long lines are truncated properly."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")

    # Create a note with a very long line
    long_line = "x" * 500 + "[[Link]]" + "y" * 500
    note = vault_root / "Projects" / "Long.md"
    note.write_text(long_line)

    from wks.vault.indexer import VaultLinkScanner

    scanner = VaultLinkScanner(vault)
    records = scanner.scan()

    # Line should be truncated
    for record in records:
        assert len(record.raw_line) <= 401  # MAX_LINE_PREVIEW + ellipsis


def test_vault_note_default_resolution(vault_root):
    """Test that unrecognized patterns default to vault_note."""
    vault = ObsidianVault(vault_path=vault_root, base_dir="WKS")
    resolver = LinkResolver(vault.links_dir)

    result = resolver.resolve("SomeRandomNote")
    assert result.status == STATUS_OK
    assert result.target_uri == "vault:///SomeRandomNote"
