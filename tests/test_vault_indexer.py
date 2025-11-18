from pathlib import Path

import mongomock
import pytest

from wks.vault.obsidian import ObsidianVault
from wks.vault.indexer import VaultLinkIndexer
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
    client = mongomock.MongoClient()
    monkeypatch.setattr("wks.vault.indexer.MongoClient", lambda *a, **k: client)
    monkeypatch.setattr("wks.vault.status_controller.MongoClient", lambda *a, **k: client)
    from mongomock.collection import BulkOperationBuilder

    original = BulkOperationBuilder.add_update

    def wrapper(self, selector, document, check_keys, upsert, **kwargs):
        return original(self, selector, document, check_keys, upsert)

    monkeypatch.setattr(BulkOperationBuilder, "add_update", wrapper)
    return client


def test_vault_link_indexer_and_status(vault, vault_root, patched_mongo):
    cfg = {"vault": {"database": "wks.vault"}, "db": {"uri": "mongodb://localhost:27017/"}}
    indexer = VaultLinkIndexer(vault, mongo_uri=cfg["db"]["uri"], collection_key=cfg["vault"]["database"])
    result = indexer.sync()
    assert result.stats.edge_total == 2
    mongo_coll = patched_mongo["wks"]["vault"]
    edge = mongo_coll.find_one({"doc_type": "link", "link_type": "wikilink"})
    assert edge["note_path"] == "Projects/Demo.md"
    assert edge["links_rel"] == "_links/papers/paper.pdf"
    assert edge["status"] == "ok"
    summary = VaultStatusController(cfg).summarize()
    assert summary.total_links == 2
    assert summary.external_urls == 1
    symlink = vault_root / "_links" / "papers" / "paper.pdf"
    symlink.unlink()
    indexer.sync()
    summary = VaultStatusController(cfg).summarize()
    assert summary.missing_symlink >= 1
    assert summary.issues
