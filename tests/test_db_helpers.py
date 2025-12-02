"""Tests for wks/db_helpers.py - database helper functions."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pymongo.errors import ServerSelectionTimeoutError

from wks.db_helpers import (
    parse_database_key,
    get_monitor_db_config,
    get_vault_db_config,
    get_transform_db_config,
    connect_to_mongo,
)


class TestParseDatabaseKey:
    """Test parse_database_key() function."""

    def test_parse_valid_key(self):
        """Test parsing valid database key format."""
        db_name, coll_name = parse_database_key("wks.monitor")
        assert db_name == "wks"
        assert coll_name == "monitor"

    def test_parse_key_with_multiple_dots(self):
        """Test parsing key with multiple dots (should split on first dot)."""
        db_name, coll_name = parse_database_key("wks.monitor.collection")
        assert db_name == "wks"
        assert coll_name == "monitor.collection"

    def test_parse_key_empty_database(self):
        """Test parsing key with empty database name raises ValueError."""
        with pytest.raises(ValueError, match="both parts non-empty"):
            parse_database_key(".monitor")

    def test_parse_key_empty_collection(self):
        """Test parsing key with empty collection name raises ValueError."""
        with pytest.raises(ValueError, match="both parts non-empty"):
            parse_database_key("wks.")

    def test_parse_key_no_dot(self):
        """Test parsing key without dot raises ValueError."""
        with pytest.raises(ValueError, match="format 'database.collection'"):
            parse_database_key("wksmonitor")

    def test_parse_key_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="format 'database.collection'"):
            parse_database_key("")


class TestGetMonitorDbConfig:
    """Test get_monitor_db_config() function."""

    def test_get_monitor_config_valid(self):
        """Test getting monitor config with valid configuration."""
        cfg = {
            "monitor": {
                "database": "wks.monitor",
            },
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        uri, db_name, coll_name = get_monitor_db_config(cfg)
        assert uri == "mongodb://localhost:27017/"
        assert db_name == "wks"
        assert coll_name == "monitor"

    def test_get_monitor_config_missing_monitor_section(self):
        """Test that missing monitor section raises KeyError."""
        cfg = {
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(KeyError, match="monitor section is required"):
            get_monitor_db_config(cfg)

    def test_get_monitor_config_missing_db_section(self):
        """Test that missing db section raises KeyError."""
        cfg = {
            "monitor": {
                "database": "wks.monitor",
            },
        }
        with pytest.raises(KeyError, match="db section is required"):
            get_monitor_db_config(cfg)

    def test_get_monitor_config_missing_db_uri(self):
        """Test that missing db.uri raises KeyError."""
        cfg = {
            "monitor": {
                "database": "wks.monitor",
            },
            "db": {},
        }
        with pytest.raises(KeyError, match="db.uri is required"):
            get_monitor_db_config(cfg)

    def test_get_monitor_config_missing_database_key(self):
        """Test that missing monitor.database raises KeyError."""
        cfg = {
            "monitor": {},
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(KeyError, match="monitor.database is required"):
            get_monitor_db_config(cfg)

    def test_get_monitor_config_invalid_database_key_format(self):
        """Test that invalid database key format raises ValueError."""
        cfg = {
            "monitor": {
                "database": "invalid",
            },
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(ValueError, match="format 'database.collection'"):
            get_monitor_db_config(cfg)


class TestGetVaultDbConfig:
    """Test get_vault_db_config() function."""

    def test_get_vault_config_valid(self):
        """Test getting vault config with valid configuration."""
        cfg = {
            "vault": {
                "database": "wks.vault",
            },
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        uri, db_name, coll_name = get_vault_db_config(cfg)
        assert uri == "mongodb://localhost:27017/"
        assert db_name == "wks"
        assert coll_name == "vault"

    def test_get_vault_config_missing_vault_section(self):
        """Test that missing vault section raises KeyError."""
        cfg = {
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(KeyError, match="vault section is required"):
            get_vault_db_config(cfg)

    def test_get_vault_config_missing_db_section(self):
        """Test that missing db section raises KeyError."""
        cfg = {
            "vault": {
                "database": "wks.vault",
            },
        }
        with pytest.raises(KeyError, match="db section is required"):
            get_vault_db_config(cfg)

    def test_get_vault_config_missing_db_uri(self):
        """Test that missing db.uri raises KeyError."""
        cfg = {
            "vault": {
                "database": "wks.vault",
            },
            "db": {},
        }
        with pytest.raises(KeyError, match="db.uri is required"):
            get_vault_db_config(cfg)

    def test_get_vault_config_missing_database_key(self):
        """Test that missing vault.database raises KeyError."""
        cfg = {
            "vault": {},
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(KeyError, match="vault.database is required"):
            get_vault_db_config(cfg)

    def test_get_vault_config_invalid_database_key_format(self):
        """Test that invalid database key format raises ValueError."""
        cfg = {
            "vault": {
                "database": "invalid",
            },
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        with pytest.raises(ValueError, match="format 'database.collection'"):
            get_vault_db_config(cfg)


class TestGetTransformDbConfig:
    """Test get_transform_db_config() function."""

    def test_get_transform_config_valid(self):
        """Test getting transform config with valid configuration."""
        cfg = {
            "db": {
                "uri": "mongodb://localhost:27017/",
            },
        }
        uri, db_name, coll_name = get_transform_db_config(cfg)
        assert uri == "mongodb://localhost:27017/"
        assert db_name == "wks"
        assert coll_name == "transform"

    def test_get_transform_config_missing_db_section(self):
        """Test that missing db section raises KeyError."""
        cfg = {}
        with pytest.raises(KeyError, match="db section is required"):
            get_transform_db_config(cfg)

    def test_get_transform_config_missing_db_uri(self):
        """Test that missing db.uri raises KeyError."""
        cfg = {
            "db": {},
        }
        with pytest.raises(KeyError, match="db.uri is required"):
            get_transform_db_config(cfg)


class TestConnectToMongo:
    """Test connect_to_mongo() function."""

    @patch("wks.db_helpers.MongoClient")
    def test_connect_success(self, mock_mongo_client_class):
        """Test successful MongoDB connection."""
        mock_client = MagicMock()
        mock_client.server_info.return_value = {"version": "5.0.0"}
        mock_mongo_client_class.return_value = mock_client

        result = connect_to_mongo("mongodb://localhost:27017/")

        mock_mongo_client_class.assert_called_once_with(
            "mongodb://localhost:27017/",
            serverSelectionTimeoutMS=5000
        )
        mock_client.server_info.assert_called_once()
        assert result == mock_client

    @patch("wks.db_helpers.MongoClient")
    def test_connect_with_custom_timeout(self, mock_mongo_client_class):
        """Test connection with custom timeout."""
        mock_client = MagicMock()
        mock_client.server_info.return_value = {"version": "5.0.0"}
        mock_mongo_client_class.return_value = mock_client

        result = connect_to_mongo("mongodb://localhost:27017/", timeout_ms=10000)

        mock_mongo_client_class.assert_called_once_with(
            "mongodb://localhost:27017/",
            serverSelectionTimeoutMS=10000
        )
        assert result == mock_client

    @patch("wks.db_helpers.MongoClient")
    def test_connect_timeout_failure(self, mock_mongo_client_class):
        """Test connection failure due to timeout."""
        mock_client = MagicMock()
        mock_client.server_info.side_effect = ServerSelectionTimeoutError("Connection timeout")
        mock_mongo_client_class.return_value = mock_client

        with pytest.raises(ServerSelectionTimeoutError, match="Connection timeout"):
            connect_to_mongo("mongodb://invalid:27017/", timeout_ms=1000)

    @patch("wks.db_helpers.MongoClient")
    def test_connect_connection_error(self, mock_mongo_client_class):
        """Test connection failure with generic exception."""
        mock_client = MagicMock()
        mock_client.server_info.side_effect = Exception("Connection refused")
        mock_mongo_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Connection refused"):
            connect_to_mongo("mongodb://localhost:27017/")
