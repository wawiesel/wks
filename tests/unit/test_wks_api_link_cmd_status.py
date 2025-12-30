"""Unit tests for wks.api.link.cmd_status."""

from tests.unit.conftest import run_cmd
from wks.api.link.cmd_status import cmd_status


def test_cmd_status_success(tracked_wks_config):
    """Test successful link status (lines 14-45)."""
    # Seed edges
    from wks.api.database.Database import Database

    with Database(tracked_wks_config.database, "edges") as db:
        db.insert_many(
            [
                {"from_local_uri": "a", "to_local_uri": "b"},
                {"from_local_uri": "a", "to_local_uri": "c", "to_remote_uri": "http://rem"},
            ]
        )

    result = run_cmd(cmd_status)
    assert result.success is True
    assert result.output["total_links"] == 2
    assert result.output["total_files"] == 3  # a, b, c
