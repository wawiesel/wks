from tests.unit.conftest import run_cmd
from wks.api.database.Database import Database
from wks.api.link.cmd_show import cmd_show


def test_cmd_show_directions(tracked_wks_config):
    """Test cmd_show with different directions (lines 31-38)."""
    # Seed DB
    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "from_local_uri": "file://a",
                    "to_local_uri": "file://b",
                    "from_remote_uri": None,
                    "to_remote_uri": None,
                    "line_number": 1,
                    "column_number": 1,
                    "parser": "test",
                    "name": "link1",
                },
                {
                    "from_local_uri": "file://b",
                    "to_local_uri": "file://c",
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
    result = run_cmd(cmd_show, uri="file://a", direction="from")
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["to_local_uri"] == "file://b"

    # Test 'to' direction
    result = run_cmd(cmd_show, uri="file://b", direction="to")
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["from_local_uri"] == "file://a"

    # Test 'both' direction
    result = run_cmd(cmd_show, uri="file://b", direction="both")
    assert result.success is True
    assert len(result.output["links"]) == 2
