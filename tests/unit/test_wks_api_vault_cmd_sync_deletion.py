import json
from typing import Any

import mongomock
import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.Database import Database
from wks.api.database.DatabaseConfig import DatabaseConfig
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


@pytest.fixture
def shared_mongo(monkeypatch):
    # Ensure module is loaded
    import wks.api.database._mongomock._Backend as backend_mod

    client: Any = mongomock.MongoClient()
    # Force the backend to use our client
    monkeypatch.setattr(backend_mod, "_get_mongomock_client", lambda: client)
    return client


def test_vault_sync_removes_deleted_notes(monkeypatch, tmp_path, minimal_config_dict, shared_mongo):
    """Vault sync should remove links from notes that no longer exist."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # 1. Manually seed DB with a "stale" link
    from wks.utils.uri_utils import path_to_uri

    stale_note = vault_dir / "note.md"
    stale_uri = path_to_uri(stale_note)

    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        db.insert_many([{"doc_type": "link", "from_local_uri": stale_uri, "to_uri": "vault:///foo"}])

    # 2. Sync (note.md does NOT exist on disk, so it should be pruned)
    res = run_cmd(cmd_sync)
    assert res.success, f"Sync fail: {res.output.get('errors')}"

    # 3. Verify deleted
    assert res.output["links_deleted"] > 0
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        assert db.find_one({"from_local_uri": stale_uri}) is None


def test_vault_sync_partial_scope_pruning(monkeypatch, tmp_path, minimal_config_dict, shared_mongo):
    """Partially syncing a folder shouldn't prune links in other folders."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Setup: root note and subdir note on disk (only valid ones)
    subdir = vault_dir / "sub"
    subdir.mkdir()
    (vault_dir / "root.md").write_text("", encoding="utf-8")
    (subdir / "nested.md").write_text("", encoding="utf-8")
    # deleted.md is NOT created on disk

    # URIs
    from wks.utils.uri_utils import path_to_uri

    root_uri = path_to_uri(vault_dir / "root.md")
    nested_uri = path_to_uri(subdir / "nested.md")
    deleted_uri = path_to_uri(subdir / "deleted.md")

    # Seed DB with all 3
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        db.insert_many(
            [
                {"doc_type": "link", "from_local_uri": root_uri},
                {"doc_type": "link", "from_local_uri": nested_uri},
                {"doc_type": "link", "from_local_uri": deleted_uri},
            ]
        )

    # Sync ONLY 'sub' directory
    run_cmd(cmd_sync, path=str(subdir))
    # Verify:
    # 1. root.md should STILL exist (pruning scoped to 'sub')
    # 2. nested.md IS GONE because file is empty -> 0 links. (Correct behavior)
    # 3. deleted.md should be GONE (was in scope 'sub' and missing from disk)
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        assert db.find_one({"from_local_uri": root_uri}) is not None
        # nested.md is gone because empty content = 0 links
        assert db.find_one({"from_local_uri": deleted_uri}) is None
