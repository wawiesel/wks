"""Unit tests for wks.api.db.helpers module."""

import pytest
from unittest.mock import MagicMock, patch

from wks.api.db.get_database_client import get_database_client
from wks.api.db.get_database import get_database
from wks.api.db.DbCollection import DbCollection
from wks.api.db.DbConfig import DbConfig

pytestmark = pytest.mark.db


def build_db_config(type: str = "mongo", prefix: str = "wks", uri: str = "mongodb://localhost:27017/"):
    """Build a DbConfig for testing."""
    if type == "mongo":
        data = {"uri": uri}
    elif type == "mongomock":
        data = {}
    else:
        data = {}
    return DbConfig(
        type=type,
        prefix=prefix,
        data=data
    )




class TestGetDatabaseClient:
    """Test get_database_client function."""

    def test_get_database_client(self, monkeypatch):
        """Test get_database_client returns client."""
        db_config = build_db_config(prefix="wks")

        mock_client = MagicMock()
        mock_collection_instance = MagicMock()
        mock_collection_instance.get_client = MagicMock(return_value=mock_client)
        mock_collection_instance.__enter__ = MagicMock(return_value=mock_collection_instance)
        mock_collection_instance.__exit__ = MagicMock(return_value=False)
        
        with patch('wks.api.db.get_database_client.DbCollection', return_value=mock_collection_instance) as mock_db_collection_class:
            result = get_database_client(db_config)
            assert result == mock_client
            mock_collection_instance.get_client.assert_called_once()
            mock_db_collection_class.assert_called_once_with(db_config, "_")

    def test_get_database_client_uses_prefix(self, monkeypatch):
        """Test get_database_client uses prefix from config."""
        db_config = build_db_config(prefix="custom")

        mock_client = MagicMock()
        mock_collection_instance = MagicMock()
        mock_collection_instance.get_client = MagicMock(return_value=mock_client)
        mock_collection_instance.__enter__ = MagicMock(return_value=mock_collection_instance)
        mock_collection_instance.__exit__ = MagicMock(return_value=False)
        
        with patch('wks.api.db.get_database_client.DbCollection', return_value=mock_collection_instance) as mock_db_collection_class:
            result = get_database_client(db_config)
            assert result == mock_client
            # Verify DbCollection was called with db_config and "_" (dummy collection name)
            mock_db_collection_class.assert_called_once_with(db_config, "_")


class TestGetDatabase:
    """Test get_database function."""

    def test_get_database(self, monkeypatch):
        """Test get_database returns database object."""
        db_config = build_db_config(prefix="wks")

        mock_db = MagicMock()
        mock_collection_instance = MagicMock()
        mock_collection_instance.get_database = MagicMock(return_value=mock_db)
        mock_collection_instance.__enter__ = MagicMock(return_value=mock_collection_instance)
        mock_collection_instance.__exit__ = MagicMock(return_value=False)
        
        with patch('wks.api.db.get_database.DbCollection', return_value=mock_collection_instance) as mock_db_collection_class:
            result = get_database(db_config, "testdb")
            assert result == mock_db
            mock_collection_instance.get_database.assert_called_once_with("testdb")
            mock_db_collection_class.assert_called_once_with(db_config, "_")

    def test_get_database_with_prefix(self, monkeypatch):
        """Test get_database with custom database name."""
        db_config = build_db_config(prefix="wks")

        mock_db = MagicMock()
        mock_collection_instance = MagicMock()
        mock_collection_instance.get_database = MagicMock(return_value=mock_db)
        mock_collection_instance.__enter__ = MagicMock(return_value=mock_collection_instance)
        mock_collection_instance.__exit__ = MagicMock(return_value=False)
        
        with patch('wks.api.db.get_database.DbCollection', return_value=mock_collection_instance) as mock_db_collection_class:
            result = get_database(db_config, "customdb")
            assert result == mock_db
            mock_collection_instance.get_database.assert_called_once_with("customdb")
            mock_db_collection_class.assert_called_once_with(db_config, "_")

