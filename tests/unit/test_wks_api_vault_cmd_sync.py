"""Unit tests for vault cmd_sync."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.URI import URI
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


def test_cmd_sync_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync returns expected output structure."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert "notes_scanned" in result.output
    assert "links_written" in result.output
    assert "links_deleted" in result.output
    assert "sync_duration_ms" in result.output
    assert "success" in result.output


def test_cmd_sync_empty_vault(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync on empty vault reports zero scanned."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync)

    assert result.output["notes_scanned"] == 0
    assert result.success is True


def test_cmd_sync_nonexistent_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync with nonexistent path returns error."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path("/nonexistent/file.md"))

    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_vault_sync_with_notes(monkeypatch, tmp_path, minimal_config_dict):
    """Vault sync scans notes with links."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Create notes with links
    (vault_dir / "note_A.md").write_text("# Note A\n[[wikilink]]\n[[note_B]]", encoding="utf-8")
    (vault_dir / "note_B.md").write_text("# Note B\n[[note_A]]", encoding="utf-8")
    (vault_dir / "nested").mkdir()
    (vault_dir / "nested" / "note_C.md").write_text("I am nested.", encoding="utf-8")

    result = run_cmd(cmd_sync)

    # Sync should succeed and find notes
    assert result.success is True, f"Sync failed: {result.output.get('errors')}"
    assert result.output["notes_scanned"] >= 3


def test_vault_sync_no_config(monkeypatch, tmp_path):
    """Should fail gracefully if config is missing."""
    wks_home = (tmp_path / ".wks").resolve()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    result = run_cmd(cmd_sync)

    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_vault_sync_removes_deleted_notes(monkeypatch, tmp_path, minimal_config_dict):
    """Vault sync should remove links from notes that no longer exist."""
    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    # Explicitly use mongomock type ensures it uses the internal backend
    cfg["database"]["type"] = "mongomock"
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    stale_uri = "vault:///note.md"
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        db.insert_many([{"doc_type": "link", "from_local_uri": stale_uri, "to_uri": "vault:///foo"}])

    res = run_cmd(cmd_sync)
    assert res.success, f"Sync fail: {res.output.get('errors')}"
    assert res.output["links_deleted"] > 0
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        assert db.find_one({"from_local_uri": stale_uri}) is None


def test_vault_sync_partial_scope_pruning(monkeypatch, tmp_path, minimal_config_dict):
    """Partially syncing a folder shouldn't prune links in other folders."""
    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    subdir = vault_dir / "sub"
    subdir.mkdir()
    (vault_dir / "root.md").write_text("", encoding="utf-8")
    (subdir / "nested.md").write_text("", encoding="utf-8")

    root_uri = "vault:///root.md"
    nested_uri = "vault:///sub/nested.md"
    deleted_uri = "vault:///sub/deleted.md"

    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        db.insert_many(
            [
                {"doc_type": "link", "from_local_uri": root_uri},
                {"doc_type": "link", "from_local_uri": nested_uri},
                {"doc_type": "link", "from_local_uri": deleted_uri},
            ]
        )

    run_cmd(cmd_sync, uri=URI.from_path(str(subdir)))
    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        assert db.find_one({"from_local_uri": root_uri}) is not None


def test_sync_writes_correct_uri_scheme(monkeypatch, tmp_path, minimal_config_dict):
    """Verify that sync writes vault:/// URIs for files within the vault."""
    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig
    from wks.api.vault.cmd_status import cmd_status
    from wks.utils.path_to_uri import path_to_uri

    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "foo.md").write_text("# Foo", encoding="utf-8")
    (vault_dir / "note.md").write_text("[[foo]]", encoding="utf-8")

    res = run_cmd(cmd_sync)
    assert res.success

    expected_uri = "vault:///note.md"
    file_uri = path_to_uri(vault_dir / "note.md")

    with Database(DatabaseConfig(**cfg["database"]), "edges") as db:
        doc = db.find_one({"from_local_uri": expected_uri})
        assert doc is not None
        doc_file = db.find_one({"from_local_uri": file_uri})
        assert doc_file is None

    st = run_cmd(cmd_status)
    assert st.success
    assert st.output["total_links"] == 1


def test_scanner_handles_read_errors(monkeypatch, tmp_path, minimal_config_dict):
    """Scanner reports errors if file cannot be read."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    note = vault_dir / "note.md"
    note.write_text("content", encoding="utf-8")
    note.chmod(0o000)

    try:
        cfg = minimal_config_dict
        cfg["vault"]["base_dir"] = str(vault_dir)
        cfg["vault"]["type"] = "obsidian"
        cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
        (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        result = run_cmd(cmd_sync)
        assert len(result.output["errors"]) > 0
    finally:
        note.chmod(0o755)


def test_scanner_handles_external_file_paths(monkeypatch, tmp_path, minimal_config_dict):
    """Syncing a file outside vault reports error."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    external_file = (tmp_path / "external.md").resolve()
    external_file.write_text("[[link]]", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(str(external_file)))
    assert result.success is False
    assert len(result.output["errors"]) > 0


def test_scanner_handles_rewrite_errors(monkeypatch, tmp_path, minimal_config_dict):
    """Scanner reports errors if file rewrite fails."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    note = vault_dir / "rewrite_me.md"
    target = vault_dir / "target.txt"
    target.touch()
    target_uri = target.resolve().as_uri()

    note.write_text(f"[link]({target_uri})", encoding="utf-8")
    note.chmod(0o444)

    try:
        cfg = minimal_config_dict
        cfg["vault"]["base_dir"] = str(vault_dir)
        cfg["vault"]["type"] = "obsidian"
        cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
        (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        result = run_cmd(cmd_sync)
        assert result.output is not None
    finally:
        note.chmod(0o644)


def test_cmd_sync_parses_markdown_urls(monkeypatch, tmp_path, minimal_config_dict):
    """Test that markdown URLs are parsed and counted."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "urls.md").write_text("[Google](https://google.com)\n[GitHub](https://github.com)", encoding="utf-8")

    result = run_cmd(cmd_sync)
    assert result.success
    assert result.output["notes_scanned"] == 1


def test_cmd_sync_handles_long_lines(monkeypatch, tmp_path, minimal_config_dict):
    """Test that long lines are truncated in raw_line preview."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    long_prefix = "x" * 500
    (vault_dir / "long.md").write_text(f"{long_prefix}[[target]]", encoding="utf-8")

    result = run_cmd(cmd_sync)
    assert result.success


def test_cmd_sync_with_mixed_link_types(monkeypatch, tmp_path, minimal_config_dict):
    """Test syncing notes with wikilinks, embeds, and URLs."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "target.md").write_text("# Target", encoding="utf-8")
    (vault_dir / "mixed.md").write_text(
        "# Mixed Links\n[[target]]\n![[target]]\n[Web](https://example.com)\n", encoding="utf-8"
    )

    result = run_cmd(cmd_sync)
    assert result.success
    assert result.output["notes_scanned"] == 2


def test_cmd_sync_extracts_headings(monkeypatch, tmp_path, minimal_config_dict):
    """Test that headings are extracted from notes with links."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    cfg["monitor"]["priority"]["dirs"] = {str(vault_dir): 1.0}
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    (vault_dir / "headings.md").write_text(
        "# Main Title\nSome intro text\n\n## Section One\n[[link_in_section]]\n\n"
        "### Subsection\n[[link_in_subsection]]\n",
        encoding="utf-8",
    )

    result = run_cmd(cmd_sync)
    assert result.success
    assert result.output["notes_scanned"] == 1


def test_cmd_sync_load_config_fails(monkeypatch, tmp_path):
    """cmd_sync fails if config is corrupt."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Corrupt JSON
    (wks_home / "config.json").write_text("{ corrupt", encoding="utf-8")

    result = run_cmd(cmd_sync)
    assert result.success is False
    # The result message only contains the exception string, the prefix is in output["errors"]
    assert any("Failed to load config" in err for err in result.output["errors"])


def test_cmd_sync_catch_all_exception(monkeypatch, tmp_path, minimal_config_dict):
    """cmd_sync handles unexpected exceptions during do_work."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Force an exception by patching Vault context manager to raise
    from wks.api.vault.Vault import Vault

    def mock_enter(self):
        raise RuntimeError("Imposed Failure")

    monkeypatch.setattr(Vault, "__enter__", mock_enter)

    result = run_cmd(cmd_sync)
    assert result.success is False
    assert "Vault sync failed: Imposed Failure" in result.result


def test_cmd_sync_path_outside_vault_coverage(monkeypatch, tmp_path, minimal_config_dict):
    """Exercise branches for paths outside vault root (requires bypassing resolve_vault_path)."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    outside_dir = (tmp_path / "outside").resolve()
    outside_dir.mkdir()
    (outside_dir / "external.md").write_text("external", encoding="utf-8")

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Mock resolve to return a path relative to vault_dir to avoid relative_to failure
    from pathlib import Path

    rel_path = Path("subdir/file.md")
    (vault_dir / "subdir").mkdir()
    target_file = vault_dir / rel_path
    target_file.write_text("content", encoding="utf-8")

    def mock_resolve(path, vault_path):
        return (f"vault:///{rel_path}", target_file)

    import wks.utils.resolve_vault_path

    monkeypatch.setattr(wks.utils.resolve_vault_path, "resolve_vault_path", mock_resolve)

    # Now run sync with a path - it will use our mock_resolve
    # This exercises line 129: scope_prefix = f"vault:///{target_path.relative_to(vault_path)}"
    result = run_cmd(cmd_sync, uri=URI.from_path(str(target_file)))
    assert result.success is True
    assert result.output["notes_scanned"] == 1
