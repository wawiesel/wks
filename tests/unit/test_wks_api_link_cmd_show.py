import os
from pathlib import Path

from tests.unit.conftest import run_cmd
from wks.api.database.Database import Database
from wks.api.link.cmd_show import cmd_show
from wks.utils.path_to_uri import path_to_uri


def test_cmd_show_directions(tracked_wks_config):
    """Test cmd_show with different directions (lines 31-38)."""
    # Seed DB
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "from_local_uri": "a",
                    "to_local_uri": "b",
                    "from_remote_uri": None,
                    "to_remote_uri": None,
                    "line_number": 1,
                    "column_number": 1,
                    "parser": "test",
                    "name": "link1",
                },
                {
                    "from_local_uri": "b",
                    "to_local_uri": "c",
                    "from_remote_uri": None,
                    "to_remote_uri": None,
                    "line_number": 2,
                    "column_number": 2,
                    "parser": "test",
                    "name": "link2",
                },
            ]
        )

    # Test 'from' direction
    result = run_cmd(cmd_show, uri="a", direction="from")
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["to_local_uri"] == "b"

    # Test 'to' direction
    result = run_cmd(cmd_show, uri="b", direction="to")
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["from_local_uri"] == "a"

    # Test 'both' direction
    result = run_cmd(cmd_show, uri="b", direction="both")
    assert result.success is True
    assert len(result.output["links"]) == 2


def test_cmd_show_resolves_relative_paths(tracked_wks_config, tmp_path):
    """Test that cmd_show resolves relative file paths to URIs for querying."""
    # Create a dummy file
    dummy_file = tmp_path / "README.md"
    dummy_file.touch()

    # Store the expected URI in the DB
    expected_uri = path_to_uri(dummy_file)

    # Seed DB with a link FROM this file
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_one(
            {
                "from_local_uri": expected_uri,
                "to_local_uri": "http://example.com",
                "from_remote_uri": None,
                "to_remote_uri": None,
                "line_number": 1,
                "column_number": 1,
                "parser": "test",
                "name": "link1",
            }
        )

    # Change CWD to tmp_path so "README.md" is a valid relative path
    orig_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        # Run cmd_show with relative path
        result = run_cmd(cmd_show, uri="README.md", direction="from")

        # Expect success and finding the link
        assert result.success is True
        assert len(result.output["links"]) == 1
        assert result.output["links"][0]["from_local_uri"] == expected_uri
    finally:
        os.chdir(orig_cwd)
