from unittest.mock import MagicMock, patch

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_list import cmd_list
from wks.api.database.cmd_prune import cmd_prune


def test_cmd_list_list_databases_error(tracked_wks_config):
    """Test error in cmd_list when list_databases fails (line 61)."""
    with patch("wks.api.database.cmd_list.Database.list_databases", side_effect=Exception("List error")):
        result = run_cmd(cmd_list)
        assert not result.success
        assert "List error" in result.output["errors"][0]


def test_cmd_prune_handler_error(tracked_wks_config):
    """Test cmd_prune handles error from a handler (lines 83-84)."""

    # Mock import_module to return a mock module whose prune() raises Exception
    mock_module = MagicMock()
    mock_module.prune.side_effect = Exception("Prune failed")

    with patch("wks.api.database.cmd_prune.import_module", return_value=mock_module):
        # We need at least one target to trigger the loop
        result = run_cmd(cmd_prune, database="nodes")
        assert result.success is True  # It reports as warning, not failure
        assert "Prune failed" in str(result.output["warnings"])


def test_set_last_prune_timestamp_read_error(tracked_wks_config, monkeypatch, tmp_path):
    """Test catch of error in set_last_prune_timestamp when reading status (lines 22-23)."""
    from wks.api.database._get_status_path import _get_status_path
    from wks.api.database._set_last_prune_timestamp import set_last_prune_timestamp

    monkeypatch.setenv("WKS_HOME", str(tmp_path))
    status_path = _get_status_path()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("invalid json", encoding="utf-8")

    # This should not raise thanks to contextlib.suppress(Exception)
    set_last_prune_timestamp("nodes")
    # And it should have overwritten with valid JSON now
    import json

    data = json.loads(status_path.read_text())
    assert "prune_timestamps" in data
    assert "nodes" in data["prune_timestamps"]
