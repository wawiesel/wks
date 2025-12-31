"""Unit tests for database cmd_reset."""

from unittest.mock import MagicMock, patch

import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_reset import cmd_reset

pytestmark = pytest.mark.database


class TestCmdReset:
    def test_cmd_reset_success(self, tracked_wks_config):
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 5
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)
        with patch("wks.api.database.cmd_reset.Database", return_value=mock_collection):
            result = run_cmd(cmd_reset, "nodes")
            assert result.success
            assert result.output["deleted_count"] == 5
            mock_collection.delete_many.assert_called_once_with({})

    def test_cmd_reset_empty_collection(self, tracked_wks_config):
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 0
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)
        with patch("wks.api.database.cmd_reset.Database", return_value=mock_collection):
            result = run_cmd(cmd_reset, "vault")
            assert result.success
            assert result.output["deleted_count"] == 0

    def test_cmd_reset_error(self, tracked_wks_config):
        mock_collection = MagicMock()
        mock_collection.delete_many.side_effect = Exception("Database error")
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)
        with patch("wks.api.database.cmd_reset.Database", return_value=mock_collection):
            result = run_cmd(cmd_reset, "nodes")
            assert not result.success
            assert "Database error" in result.output["errors"][0]
            assert result.output["deleted_count"] == 0

    def test_cmd_reset_collection_init_error(self, tracked_wks_config):
        with patch("wks.api.database.cmd_reset.Database", side_effect=Exception("Connection failed")):
            result = run_cmd(cmd_reset, "nodes")
            assert not result.success
            assert "Connection failed" in result.output["errors"][0]

    def test_cmd_reset_all(self, tracked_wks_config):
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 5
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        with (
            patch("wks.api.database.cmd_reset.Database", return_value=mock_collection) as mock_db,
        ):
            # Mock list_databases to return actual databases
            mock_db.list_databases.return_value = ["nodes", "edges"]
            result = run_cmd(cmd_reset, "all")
            assert result.success
            assert result.output["deleted_count"] == 10  # 5 * 2 (nodes, edges)
            assert mock_collection.delete_many.call_count == 2

    @pytest.mark.transform
    def test_cmd_reset_transform_clears_cache(self, wks_home, minimal_config_dict):
        """Test that resetting 'transform' database also clears fs cache."""
        from pathlib import Path

        # Setup cache dir with files
        cache_dir = Path(minimal_config_dict["transform"]["cache"]["base_dir"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "test.md").write_text("content")

        # Mock Database to avoid real connection if not needed,
        # but here we might want to use real mongo fixture?
        # Let's use mocks for DB interaction but verify real FS side effect
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 1
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        with patch("wks.api.database.cmd_reset.Database", return_value=mock_collection) as mock_db:
            mock_db.list_databases.return_value = ["transform"]

            result = run_cmd(cmd_reset, "transform")
            assert result.success

            # Verify cache file is gone
            assert not (cache_dir / "test.md").exists()
