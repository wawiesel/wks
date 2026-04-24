"""Unit tests for the shared move service layer."""

import copy

from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.services.mv import MoveRequest, move_document


def test_move_document_moves_file(monkeypatch, tracked_wks_config, tmp_path):
    """The move service should move files once policy checks pass."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()
    tracked_wks_config.monitor.filter.include_paths.extend([str(source_dir), str(dest_dir)])

    source_file = source_dir / "notes.txt"
    dest_file = dest_dir / "notes.txt"
    source_file.write_text("move me", encoding="utf-8")

    monkeypatch.setattr("wks.services.mv._update_move_side_effects", lambda *_args: (True, []))

    response = move_document(MoveRequest(source=str(source_file), dest=str(dest_file)))

    assert response.success is True
    assert response.database_updated is True
    assert dest_file.exists()
    assert not source_file.exists()


def test_move_document_rejects_existing_destination(monkeypatch, tracked_wks_config, tmp_path):
    """The move service should reject destination overwrites."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()
    tracked_wks_config.monitor.filter.include_paths.extend([str(source_dir), str(dest_dir)])

    source_file = source_dir / "notes.txt"
    dest_file = dest_dir / "notes.txt"
    source_file.write_text("move me", encoding="utf-8")
    dest_file.write_text("already here", encoding="utf-8")

    response = move_document(MoveRequest(source=str(source_file), dest=str(dest_file)))

    assert response.success is False
    assert response.failure_kind == "conflict"
    assert "Destination exists" in response.errors[0]


def test_move_document_honors_explicit_config(monkeypatch, minimal_config_dict, tmp_path):
    """The move service should keep monitor and vault side effects on the injected config."""

    def build_config(prefix: str, cache_dir, source_dir, dest_dir, vault_dir) -> WKSConfig:
        raw = copy.deepcopy(minimal_config_dict)
        raw["database"]["prefix"] = prefix
        raw["transform"]["cache"]["base_dir"] = str(cache_dir)
        raw["monitor"]["filter"]["include_paths"] = [str(source_dir), str(dest_dir), str(cache_dir)]
        raw["vault"]["base_dir"] = str(vault_dir)
        return WKSConfig.model_validate(raw)

    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    dest_dir.mkdir()

    source_file = source_dir / "2026-Notes.txt"
    dest_file = dest_dir / "2026-Notes.txt"
    source_file.write_text("move me", encoding="utf-8")

    default_config = build_config(
        "wks_default_mv",
        tmp_path / "default_cache",
        source_dir,
        dest_dir,
        tmp_path / "default_vault",
    )
    alternate_config = build_config(
        "wks_alt_mv",
        tmp_path / "alt_cache",
        source_dir,
        dest_dir,
        tmp_path / "alt_vault",
    )
    monkeypatch.setattr(WKSConfig, "load", classmethod(lambda cls: default_config))

    captured = {}

    class FakeVault:
        def __init__(self, vault_config=None):
            captured["vault_config"] = vault_config

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def update_link_for_move(self, old_path, new_path):
            return None

    monkeypatch.setattr("wks.api.vault.Vault.Vault", FakeVault)

    with Database(alternate_config.database, "nodes") as database:
        database.update_one(
            {"local_uri": str(URI.from_path(source_file))},
            {"$set": {"local_uri": str(URI.from_path(source_file))}},
            upsert=True,
        )

    response = move_document(MoveRequest(source=str(source_file), dest=str(dest_file)), config=alternate_config)

    assert response.success is True
    assert response.database_updated is True
    assert captured["vault_config"] is alternate_config.vault

    with Database(alternate_config.database, "nodes") as database:
        nodes = database.get_database()["nodes"]
        assert nodes.count_documents({"local_uri": str(URI.from_path(source_file))}) == 0
        assert nodes.count_documents({"local_uri": str(URI.from_path(dest_file))}) == 1

    with Database(default_config.database, "nodes") as database:
        nodes = database.get_database()["nodes"]
        assert nodes.count_documents({"local_uri": str(URI.from_path(dest_file))}) == 0
