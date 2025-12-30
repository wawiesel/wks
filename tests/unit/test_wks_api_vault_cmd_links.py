"""Unit tests for vault cmd_links."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault.cmd_links import cmd_links

pytestmark = pytest.mark.vault


def test_cmd_links_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """Should return basic structure for empty results."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg))

    # Create a real file in vault
    test_file = vault_dir / "note.md"
    test_file.write_text("# Test")

    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "edges") as db:
        db.delete_many({})

    result = run_cmd(cmd_links, path="note.md", direction="both")
    assert result.success is True
    assert result.output["count"] == 0
    assert result.output["edges"] == []


def test_cmd_links_finds_outgoing(monkeypatch, tmp_path, minimal_config_dict):
    """Should find outgoing links (from_uri match)."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg))

    # Create a real file in vault
    note1 = vault_dir / "note1.md"
    note1.write_text("Link to [[note2]]")

    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "edges") as db:
        db.delete_many({})
        db.get_database()["edges"].insert_one(
            {
                "from_local_uri": "vault:///note1.md",
                "to_local_uri": "vault:///note2",
                "line_number": 10,
            }
        )

    result = run_cmd(cmd_links, path="note1.md", direction="from")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["to_uri"] == "vault:///note2"


def test_cmd_links_finds_incoming(monkeypatch, tmp_path, minimal_config_dict):
    """Should find incoming links (to_uri match)."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    cfg["vault"]["type"] = "obsidian"
    (wks_home / "config.json").write_text(json.dumps(cfg))

    # Create a real file in vault
    note2 = vault_dir / "note2.md"
    note2.write_text("# Note 2")

    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "edges") as db:
        db.delete_many({})
        db.get_database()["edges"].insert_one(
            {
                "from_local_uri": "vault:///note1.md",
                "to_local_uri": "vault:///note2.md",
                "line_number": 10,
            }
        )

    result = run_cmd(cmd_links, path="note2.md", direction="to")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["from_uri"] == "vault:///note1.md"


def test_cmd_links_invalid_config(monkeypatch, tmp_path):
    """Should handle config errors gracefully."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # No config file

    result = run_cmd(cmd_links, path="foo")
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_links_path_error(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_links with invalid vault path (line 56-68)."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    result = run_cmd(cmd_links, path="../../outside.md")
    assert result.success is False
    assert "does not exist" in result.result or "not in vault" in result.result.lower()


def test_cmd_links_query_failure(monkeypatch, tmp_path, minimal_config_dict):
    """Test cmd_links with database query failure (line 112-123)."""
    wks_home = (tmp_path / ".wks").resolve()
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    vault_dir = (tmp_path / "vault").resolve()
    vault_dir.mkdir()
    # Create the file so resolve_vault_path succeeds
    (vault_dir / "test.md").touch()

    cfg = minimal_config_dict
    cfg["vault"]["base_dir"] = str(vault_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Mock Database to fail
    from wks.api.database.Database import Database

    def mock_enter(self):
        raise RuntimeError("DB Error")

    monkeypatch.setattr(Database, "__enter__", mock_enter)

    result = run_cmd(cmd_links, path="test.md")
    assert result.success is False
    assert "Query failed" in result.output["errors"][0]
