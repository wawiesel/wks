from typer.testing import CliRunner

from wks.api.database.Database import Database
from wks.cli.link import link
from wks.utils.path_to_uri import path_to_uri

runner = CliRunner()


def test_link_show_cli_resolves_path(tracked_wks_config, tmp_path):
    # Setup DB
    dummy_file = tmp_path / "README.md"
    dummy_file.touch()
    expected_uri = path_to_uri(dummy_file)

    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_one(
            {
                "from_local_uri": expected_uri,
                "to_local_uri": "https://example.com",
                "from_remote_uri": None,
                "to_remote_uri": None,
                "line_number": 1,
                "column_number": 1,
                "parser": "test",
                "name": "link1",
            }
        )

    # Run CLI
    result = runner.invoke(link(), ["show", str(dummy_file)])
    assert result.exit_code == 0
    assert "https://example.com" in result.stdout
    assert expected_uri in result.stdout


def test_link_show_cli_fails_missing_file(tracked_wks_config):
    result = runner.invoke(link(), ["show", "nonexistent.md"])
    assert result.exit_code == 2
    assert "Path 'nonexistent.md' does not exist" in result.stderr
