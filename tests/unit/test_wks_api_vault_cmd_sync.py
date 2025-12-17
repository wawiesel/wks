"""Unit tests for vault cmd_sync."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


def test_cmd_sync_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync returns expected output structure."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert "notes_scanned" in result.output
    assert "edges_written" in result.output
    assert "edges_deleted" in result.output
    assert "sync_duration_ms" in result.output
    assert "success" in result.output


def test_cmd_sync_empty_vault(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync on empty vault reports zero scanned."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert result.output["notes_scanned"] == 0
    assert result.success is True


def test_cmd_sync_nonexistent_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync with nonexistent path returns error."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync, path="/nonexistent/file.md")

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_vault_sync_full_coverage(monkeypatch, tmp_path, minimal_config_dict):
    """Exercise all branches of markdown parsing and linking."""
    # Setup WKS HOME and Config
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Configure vault base dir
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # --- Create Complex Vault Content ---

    # Create external file for file:// link
    ext_file = tmp_path / "external_doc.txt"
    ext_file.write_text("External Content", encoding="utf-8")
    ext_file_uri = ext_file.as_uri()  # file:///...

    # 1. Standard Note with various link types
    (vault_dir / "note_A.md").write_text(
        f"""# Note A
        This is a [[wikilink]].
        This is a [[wikilink|aliased]].
        This is a [[note_B#anchor]].
        This is a [markdown link](note_C.md).
        This is an [external link](https://google.com).
        This is a [[broken link]].
        This is a [file link]({ext_file_uri}).
        This is a [[_links/machine/symlink.md]].
        """,
        encoding="utf-8",
    )

    # 2. Target Note B (exists)
    (vault_dir / "note_B.md").write_text("# Note B\nBacklink to [[note_A]].", encoding="utf-8")

    # 3. Target Note C (exists, linking to subfolder)
    (vault_dir / "note_C.md").write_text("See [[nested/note_D]].", encoding="utf-8")

    # 4. Nested structure
    (vault_dir / "nested").mkdir()
    (vault_dir / "nested" / "note_D.md").write_text("I am nested.", encoding="utf-8")

    # 5. Non-markdown file (should be ignored or handled differently)
    (vault_dir / "image.png").write_bytes(b"fake image data")

    # 6. File with tricky name
    (vault_dir / "My Note With Spaces.md").write_text("[[note_A]]", encoding="utf-8")

    # --- Run Sync ---
    result = run_cmd(cmd_sync)

    assert result.success is True, f"Sync failed: {result.output.get('errors')}"
    # notes_scanned should be at least 4 (note_A, note_B, note_C, note_D)
    assert result.output["notes_scanned"] >= 4

    # --- Verify Database State ---
    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**cfg["database"])
    with Database(db_config, "wks.vault") as db:
        # Check edges
        edges = list(db.find({"doc_type": "link"}))
        assert len(edges) > 0

        # Verify specific edges
        # [[wikilink]] -> implicit destination "wikilink" (status OK by default in current impl)
        wiki_links = [e for e in edges if e["to_uri"] == "vault:///wikilink"]
        assert len(wiki_links) > 0
        assert wiki_links[0]["status"] == "ok"

        # [[broken link]] -> implicit destination "broken link"
        broken_links = [e for e in edges if e["to_uri"] == "vault:///broken link"]
        assert len(broken_links) > 0
        assert broken_links[0]["status"] == "ok"

        # [file link](file:///...) -> _links/... -> vault:///...
        # Should persist as vault:///... or similar depending on resolution
        # We expect at least the attempt to parse it

        # [[note_B#anchor]] -> to vault:///note_B#anchor (naive resolver)
        note_b_links = [e for e in edges if e["to_uri"] == "vault:///note_B#anchor"]
        assert len(note_b_links) > 0
        # [markdown link](note_C.md) -> note_C.md (raw url for markdown links)
        note_c_links = [e for e in edges if e["to_uri"] == "note_C.md"]
        all_uris = [e["to_uri"] for e in edges]
        assert len(note_c_links) > 0, f"Expected note_C.md in edges. Warning: Found {all_uris}"


def test_vault_sync_no_config(monkeypatch, tmp_path):
    """Should fail gracefully if config is missing."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # No config file created

    result = run_cmd(cmd_sync)

    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_vault_sync_db_failure(monkeypatch, tmp_path, minimal_config_dict):
    """Should fail gracefully if database is unreachable."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_config_dict
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Mock DB Connection Failure
    class BrokenDB:
        def __init__(*args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("Connection Refused")

        def __exit__(*args):
            pass

    monkeypatch.setattr("wks.api.vault.cmd_sync.Database", BrokenDB)

    result = run_cmd(cmd_sync)

    assert result.success is False
    # Errors list contains the exception message
    assert any("Connection Refused" in e for e in result.output["errors"])
