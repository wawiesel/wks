"""Unit tests for wks.api.db.cmd_list module."""

from unittest.mock import MagicMock, patch

import pytest

from wks.api.db.cmd_list import cmd_list

pytestmark = pytest.mark.db


class TestCmdList:
    """Test cmd_list function."""

    def test_cmd_list_success(self, monkeypatch):
        """Test cmd_list with successful collection listing."""
        mock_collection_names = ["wks.monitor", "wks.vault", "wks.transform"]

        mock_impl = MagicMock()
        mock_impl.list_collection_names.return_value = mock_collection_names

        mock_collection = MagicMock()
        mock_collection._impl = mock_impl
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config) as mock_load:
            with patch("wks.api.db.cmd_list.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_list()

        assert result.success is True
        assert "Found 3 collection(s)" in result.result
        assert set(result.output["collections"]) == {"monitor", "vault", "transform"}

    def test_cmd_list_no_prefix_collections(self, monkeypatch):
        """Test cmd_list with collections that don't have prefix."""
        mock_collection_names = ["custom.collection", "other.collection"]

        mock_impl = MagicMock()
        mock_impl.list_collection_names.return_value = mock_collection_names

        mock_collection = MagicMock()
        mock_collection._impl = mock_impl
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_list.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_list()

        assert result.success is True
        assert result.output["collections"] == ["custom.collection", "other.collection"]

    def test_cmd_list_empty(self, monkeypatch):
        """Test cmd_list when no collections exist."""
        mock_impl = MagicMock()
        mock_impl.list_collection_names.return_value = []

        mock_collection = MagicMock()
        mock_collection._impl = mock_impl
        mock_collection.__enter__ = MagicMock(return_value=mock_collection)
        mock_collection.__exit__ = MagicMock(return_value=False)

        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_list.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.return_value = mock_collection
                result = cmd_list()

        assert result.success is True
        assert "Found 0 collection(s)" in result.result
        assert result.output["collections"] == []

    def test_cmd_list_error(self, monkeypatch):
        """Test cmd_list when database access fails."""
        mock_config = MagicMock()
        mock_config.db.prefix = "wks"
        with patch("wks.api.config.WKSConfig.WKSConfig.load", return_value=mock_config):
            with patch("wks.api.db.cmd_list.DbCollection") as mock_db_collection_class:
                mock_db_collection_class.side_effect = Exception("Connection failed")
                result = cmd_list()

        assert result.success is False
        assert "Failed to list collections" in result.result
        assert "error" in result.output
        assert "Connection failed" in result.output["error"]
        assert result.output["collections"] == []
