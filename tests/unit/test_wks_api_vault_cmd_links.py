import pytest

from tests.unit._vault_test_helpers import setup_vault_env, vault_database_config
from tests.unit.conftest import run_cmd
from wks.api.config.URI import URI
from wks.api.vault.cmd_links import cmd_links

pytestmark = pytest.mark.vault


def test_cmd_links_returns_structure(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    test_file = vault_dir / "note.md"
    test_file.write_text("# Test")

    from wks.api.database.Database import Database

    with Database(vault_database_config(config), "edges") as db:
        db.delete_many({})

    result = run_cmd(cmd_links, uri=URI("vault:///note.md"), direction="both")
    assert result.success is True
    assert result.output["count"] == 0
    assert result.output["edges"] == []


def test_cmd_links_finds_outgoing(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    note1 = vault_dir / "note1.md"
    note1.write_text("Link to [[note2]]")

    from wks.api.database.Database import Database

    with Database(vault_database_config(config), "edges") as db:
        db.delete_many({})
        db.get_database()["edges"].insert_one(
            {
                "from_local_uri": "vault:///note1.md",
                "to_local_uri": "vault:///note2",
                "line_number": 10,
            }
        )

    result = run_cmd(cmd_links, uri=URI("vault:///note1.md"), direction="from")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["to_uri"] == "vault:///note2"


def test_cmd_links_finds_incoming(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    note2 = vault_dir / "note2.md"
    note2.write_text("# Note 2")

    from wks.api.database.Database import Database

    with Database(vault_database_config(config), "edges") as db:
        db.delete_many({})
        db.get_database()["edges"].insert_one(
            {
                "from_local_uri": "vault:///note1.md",
                "to_local_uri": "vault:///note2.md",
                "line_number": 10,
            }
        )

    result = run_cmd(cmd_links, uri=URI("vault:///note2.md"), direction="to")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["from_uri"] == "vault:///note1.md"


def test_cmd_links_invalid_config(monkeypatch, tmp_path):
    monkeypatch.setenv("WKS_HOME", str(tmp_path))

    result = run_cmd(cmd_links, uri=URI("vault:///foo"))
    assert result.success is False
    assert "Failed to load config" in result.output["errors"][0]


def test_cmd_links_path_outside_vault(monkeypatch, tmp_path, minimal_config_dict):
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    result = run_cmd(cmd_links, uri=URI("vault:///../../outside.md"))
    assert result.success is True  # DB query succeeds
    assert result.output["count"] == 0  # Just no edges found


def test_cmd_links_query_failure(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, _ = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)
    (vault_dir / "test.md").touch()

    from wks.api.database.Database import Database

    def mock_enter(self):
        raise RuntimeError("DB Error")

    monkeypatch.setattr(Database, "__enter__", mock_enter)

    result = run_cmd(cmd_links, uri=URI("vault:///test.md"))
    assert result.success is False
    assert "Query failed" in result.output["errors"][0]


def test_cmd_links_file_uri_inside_vault(monkeypatch, tmp_path, minimal_config_dict):
    _, vault_dir, config = setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    note = vault_dir / "note.md"
    note.write_text("# Test")

    from wks.api.database.Database import Database

    with Database(vault_database_config(config), "edges") as db:
        db.delete_many({})
        db.get_database()["edges"].insert_one(
            {
                "from_local_uri": "vault:///note.md",
                "to_local_uri": "vault:///other.md",
                "line_number": 5,
            }
        )

    file_uri = URI.from_path(note)
    result = run_cmd(cmd_links, uri=file_uri, direction="from")

    assert result.success is True
    assert result.output["count"] == 1
    assert result.output["edges"][0]["to_uri"] == "vault:///other.md"


def test_cmd_links_non_vault_uri_error(monkeypatch, tmp_path, minimal_config_dict):
    setup_vault_env(monkeypatch, tmp_path, minimal_config_dict)

    outside_file = tmp_path / "outside.md"
    outside_file.touch()
    file_uri = URI.from_path(outside_file)

    result = run_cmd(cmd_links, uri=file_uri)
    assert result.success is False
    assert "Target is not in the vault" in result.output["errors"][0]
    assert result.output["count"] == 0
