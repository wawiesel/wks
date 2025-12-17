"""Unit tests for vault cmd_links."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.vault._constants import DOC_TYPE_LINK, STATUS_OK
from wks.api.vault.cmd_links import cmd_links

pytestmark = pytest.mark.vault


def test_cmd_links_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    """Should return basic structure even if valid."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps(minimal_config_dict | {"vault": minimal_config_dict["vault"] | {"type": "obsidian"}})
    )

    # Needs to init database even if empty
    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "wks.vault") as db:
        db.delete_many({})

    result = run_cmd(cmd_links, path="fake/path", direction="both")
    assert result.success is True
    assert result.output["count"] == 0
    assert result.output["edges"] == []


def test_cmd_links_finds_outgoing(monkeypatch, tmp_path, minimal_config_dict):
    """Should find outgoing links (from_uri match)."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps(minimal_config_dict | {"vault": minimal_config_dict["vault"] | {"type": "obsidian"}})
    )

    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "wks.vault") as db:
        db.delete_many({})
        db.get_database()["wks.vault"].insert_one(
            {
                "doc_type": DOC_TYPE_LINK,
                "from_uri": "vault:///note1.md",
                "to_uri": "note2",
                "line_number": 10,
                "status": STATUS_OK,
            }
        )

    result = run_cmd(cmd_links, path="note1.md", direction="from")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["to_uri"] == "note2"
    # Edge does not have direction field in schema


def test_cmd_links_finds_incoming(monkeypatch, tmp_path, minimal_config_dict):
    """Should find incoming links (to_uri match)."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps(minimal_config_dict | {"vault": minimal_config_dict["vault"] | {"type": "obsidian"}})
    )

    from wks.api.database.Database import Database
    from wks.api.database.DatabaseConfig import DatabaseConfig

    db_config = DatabaseConfig(**minimal_config_dict["database"])
    with Database(db_config, "wks.vault") as db:
        db.delete_many({})
        db.get_database()["wks.vault"].insert_one(
            {
                "doc_type": DOC_TYPE_LINK,
                "from_uri": "vault:///note1.md",
                "to_uri": "vault:///note2",
                "line_number": 10,
                "status": STATUS_OK,
            }
        )

    # Searching for links to "note2"
    result = run_cmd(cmd_links, path="note2", direction="to")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["from_uri"] == "vault:///note1.md"
    # Edge does not have direction field in schema


def test_cmd_links_invalid_config(monkeypatch, tmp_path):
    """Should handle config errors gracefully."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    # No config file

    result = run_cmd(cmd_links, path="foo")
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_links_database_error(monkeypatch, tmp_path, minimal_config_dict):
    """Should handle database errors gracefully."""
    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(
        json.dumps(minimal_config_dict | {"vault": minimal_config_dict["vault"] | {"type": "obsidian"}})
    )

    # Mock Database to raise exception
    class BrokenDB:
        def __init__(*args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("BOOM")

        def __exit__(*args):
            pass

    monkeypatch.setattr("wks.api.vault.cmd_links.Database", BrokenDB)

    result = run_cmd(cmd_links, path="foo")
    assert result.success is False
    assert "Query failed: BOOM" in result.output["errors"][0]
