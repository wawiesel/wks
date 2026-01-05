from typer.testing import CliRunner

from wks.api.database.Database import Database
from wks.api.URI import URI
from wks.cli.link import link

runner = CliRunner()


def test_link_show_cli_resolves_path(tracked_wks_config, tmp_path):
    # Setup DB
    dummy_file = tmp_path / "README.md"
    dummy_file.touch()
    expected_uri = str(URI.from_path(dummy_file))

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


def test_link_show_cli_allows_missing_file(tracked_wks_config):
    """Refactored: show command allows checking history for missing files."""
    result = runner.invoke(link(), ["show", "nonexistent.md"])
    assert result.exit_code == 0
    # YAML output
    assert "links: []" in result.stdout


def test_link_check_cli_wiring(tracked_wks_config, tmp_path):
    """Test link check command wiring."""
    f = tmp_path / "test.md"
    f.write_text("[link](target)", encoding="utf-8")

    # Existent file (but unmonitored)
    result = runner.invoke(link(), ["check", str(f)])
    assert result.exit_code == 0
    # YAML output
    assert "path:" in result.stdout
    assert "name: link" in result.stdout

    # Missing file -> API enforces existence -> Error (exit 1)
    result = runner.invoke(link(), ["check", "missing.md"])
    assert result.exit_code == 1
    assert "File does not exist" in result.stdout
