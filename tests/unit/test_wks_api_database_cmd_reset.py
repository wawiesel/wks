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
        with patch("wks.api.database.cmd_reset.Database", return_value=mock_collection):
            # We expect Database to be initialized multiple times (once per target)
            # Hardcoded targets in implementation is 3: nodes, edges, vault
            result = run_cmd(cmd_reset, "all")
            assert result.success
            assert result.output["deleted_count"] == 15  # 5 * 3
            assert mock_collection.delete_many.call_count == 3
