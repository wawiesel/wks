from pathlib import Path

import pytest

from tests.unit._vault_test_helpers import setup_vault_env, vault_database_config, write_unit_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.vault.cmd_sync import cmd_sync

pytestmark = pytest.mark.vault


def write_vault_notes(vault_dir: Path, notes: dict[str, str]) -> None:
    for name, content in notes.items():
        path = vault_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_cmd_sync_empty_vault_structure(monkeypatch, tmp_path, minimal_config_dict):
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)

    result = run_cmd(cmd_sync)

    assert result.success is True
    assert result.output["notes_scanned"] == 0
    assert {"notes_scanned", "links_written", "links_deleted", "sync_duration_ms", "success"} <= set(result.output)


@pytest.mark.parametrize("target", [URI.from_path("/nonexistent/file.md"), None])
def test_cmd_sync_config_and_path_failures(monkeypatch, tmp_path, minimal_config_dict, target):
    if target is None:
        wks_home = (tmp_path / ".wks").resolve()
        wks_home.mkdir()
        monkeypatch.setenv("WKS_HOME", str(wks_home))
        result = run_cmd(cmd_sync)
        assert result.success is False
        assert "Failed to load config" in result.output["errors"][0]
        return

    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    result = run_cmd(cmd_sync, uri=target)
    assert result.success is False
    assert result.output["errors"]


def test_vault_sync_with_notes(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    write_vault_notes(
        vault_dir,
        {
            "note_A.md": "# Note A\n[[wikilink]]\n[[note_B]]",
            "note_B.md": "# Note B\n[[note_A]]",
            "nested/note_C.md": "I am nested.",
        },
    )

    result = run_cmd(cmd_sync)

    assert result.success is True
    assert result.output["notes_scanned"] >= 3


def test_vault_sync_removes_deleted_notes(monkeypatch, tmp_path, minimal_config_dict):
    from wks.api.database.Database import Database

    wks_home, _, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    config["database"]["type"] = "mongomock"
    write_unit_config(wks_home, config)

    stale_uri = "vault:///note.md"
    with Database(vault_database_config(config), "edges") as db:
        db.insert_many([{"doc_type": "link", "from_local_uri": stale_uri, "to_uri": "vault:///foo"}])

    result = run_cmd(cmd_sync)

    assert result.success is True
    assert result.output["links_deleted"] > 0
    with Database(vault_database_config(config), "edges") as db:
        assert db.find_one({"from_local_uri": stale_uri}) is None


def test_vault_sync_partial_scope_pruning(monkeypatch, tmp_path, minimal_config_dict):
    from wks.api.database.Database import Database

    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    write_vault_notes(vault_dir, {"root.md": "", "sub/nested.md": ""})

    with Database(vault_database_config(config), "edges") as db:
        db.insert_many(
            [
                {"doc_type": "link", "from_local_uri": "vault:///root.md"},
                {"doc_type": "link", "from_local_uri": "vault:///sub/nested.md"},
                {"doc_type": "link", "from_local_uri": "vault:///sub/deleted.md"},
            ]
        )

    run_cmd(cmd_sync, uri=URI.from_path(str(vault_dir / "sub")))
    with Database(vault_database_config(config), "edges") as db:
        assert db.find_one({"from_local_uri": "vault:///root.md"}) is not None


def test_sync_writes_correct_uri_scheme(monkeypatch, tmp_path, minimal_config_dict):
    from wks.api.database.Database import Database
    from wks.api.vault.cmd_status import cmd_status

    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    write_vault_notes(vault_dir, {"foo.md": "# Foo", "note.md": "[[foo]]"})

    result = run_cmd(cmd_sync)

    assert result.success is True
    with Database(vault_database_config(config), "edges") as db:
        assert db.find_one({"from_local_uri": "vault:///note.md"}) is not None
        assert db.find_one({"from_local_uri": str(URI.from_path(vault_dir / "note.md"))}) is None

    status = run_cmd(cmd_status)
    assert status.success is True
    assert status.output["total_links"] == 1


def test_vault_sync_scanner_errors(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    note = vault_dir / "note.md"
    note.write_text("content", encoding="utf-8")
    note.chmod(0o000)

    rewrite_note = vault_dir / "rewrite_me.md"
    target = vault_dir / "target.txt"
    target.touch()
    rewrite_note.write_text(f"[link]({target.resolve().as_uri()})", encoding="utf-8")
    rewrite_note.chmod(0o444)

    try:
        result = run_cmd(cmd_sync)
    finally:
        note.chmod(0o755)
        rewrite_note.chmod(0o644)

    assert result.output is not None
    assert result.output["errors"]


def test_vault_sync_external_file_path_fails(monkeypatch, tmp_path, minimal_config_dict):
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)

    external_file = (tmp_path / "external.md").resolve()
    external_file.write_text("[[link]]", encoding="utf-8")

    result = run_cmd(cmd_sync, uri=URI.from_path(str(external_file)))

    assert result.success is False
    assert result.output["errors"]


def test_cmd_sync_handles_common_markdown_shapes(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict, include_priority_dir=True)
    write_vault_notes(
        vault_dir,
        {
            "urls.md": "[Google](https://google.com)\n[GitHub](https://github.com)",
            "long.md": f"{'x' * 500}[[target]]",
            "target.md": "# Target",
            "mixed.md": "# Mixed Links\n[[target]]\n![[target]]\n[Web](https://example.com)\n",
            "headings.md": (
                "# Main Title\n\n## Section One\n[[link_in_section]]\n\n### Subsection\n[[link_in_subsection]]\n"
            ),
        },
    )

    result = run_cmd(cmd_sync)

    assert result.success is True
    assert result.output["notes_scanned"] == 5


def test_cmd_sync_load_config_and_runtime_failure(monkeypatch, tmp_path, minimal_config_dict):
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text("{ corrupt", encoding="utf-8")

    broken_config_result = run_cmd(cmd_sync)
    assert broken_config_result.success is False
    assert any("Failed to load config" in err for err in broken_config_result.output["errors"])

    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)
    from wks.api.vault.Vault import Vault

    monkeypatch.setattr(Vault, "__enter__", lambda self: (_ for _ in ()).throw(RuntimeError("Imposed Failure")))

    runtime_result = run_cmd(cmd_sync)
    assert runtime_result.success is False
    assert "Vault sync failed: Imposed Failure" in runtime_result.result
