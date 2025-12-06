"""Unit tests for wks.api.db.cmd_reset module."""

from unittest.mock import MagicMock, patch

import pytest

from wks.api.db.cmd_reset import cmd_reset

pytestmark = pytest.mark.db


class TestCmdReset:
    """Test cmd_reset function."""

    def test_cmd_reset_success(self, monkeypatch):
        """Test cmd_reset with successful deletion."""
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 5
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_reset.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_reset("monitor")

        assert result.success is True
        assert "Deleted 5 document(s) from monitor" in result.result
        assert result.output["collection"] == "monitor"
        assert result.output["deleted_count"] == 5
        assert result.output["success"] is True
        mock_collection.delete_many.assert_called_once_with({})

    def test_cmd_reset_empty_collection(self, monkeypatch):
        """Test cmd_reset when collection is empty."""
        mock_collection = MagicMock()
        mock_collection.delete_many.return_value = 0
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_reset.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_reset("vault")

        assert result.success is True
        assert "Deleted 0 document(s) from vault" in result.result
        assert result.output["deleted_count"] == 0

    def test_cmd_reset_error(self, monkeypatch):
        """Test cmd_reset when deletion fails."""
        mock_collection = MagicMock()
        mock_collection.delete_many.side_effect = Exception("Database error")
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_reset.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_reset("monitor")

        assert result.success is False
        assert "Reset failed" in result.result
        assert "error" in result.output
        assert "Database error" in result.output["error"]
        assert result.output["collection"] == "monitor"
        assert result.output["success"] is False

    def test_cmd_reset_collection_init_error(self, monkeypatch):
        """Test cmd_reset when collection initialization fails."""
        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_reset.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.side_effect = Exception("Connection failed")
                result = cmd_reset("monitor")

        assert result.success is False
        assert "Reset failed" in result.result
        assert "Connection failed" in result.output["error"]
