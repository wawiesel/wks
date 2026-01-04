from tests.unit.conftest import run_cmd
from wks.api.database.Database import Database
from wks.api.link.cmd_show import Direction, cmd_show
from wks.api.URI import URI


def test_cmd_show_directions(tracked_wks_config):
    """Test cmd_show with different directions (lines 31-38)."""
    # Seed DB
    # wawiesel requires URIs of the form file://<host>/path
    host = "localhost"
    uri_a = f"file://{host}/a"
    uri_b = f"file://{host}/b"
    uri_c = f"file://{host}/c"

    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {
                    "from_local_uri": uri_a,
                    "to_local_uri": uri_b,
                    "from_remote_uri": None,
                    "to_remote_uri": None,
                    "line_number": 1,
                    "column_number": 1,
                    "parser": "test",
                    "name": "link1",
                },
                {
                    "from_local_uri": uri_b,
                    "to_local_uri": uri_c,
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
    result = run_cmd(cmd_show, uri=URI(uri_a), direction=Direction.FROM)
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["to_local_uri"] == uri_b

    # Test 'to' direction
    result = run_cmd(cmd_show, uri=URI(uri_b), direction=Direction.TO)
    assert result.success is True
    assert len(result.output["links"]) == 1
    assert result.output["links"][0]["from_local_uri"] == uri_a

    # Test 'both' direction
    result = run_cmd(cmd_show, uri=URI(uri_b), direction=Direction.BOTH)
    assert result.success is True
    assert len(result.output["links"]) == 2
