"""Unit tests for wks.api.database.DatabaseConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.database.DatabaseConfig import DatabaseConfig

pytestmark = pytest.mark.db


class TestDatabaseConfig:
    """Test DatabaseConfig class."""

    def test_database_config_mongo(self):
        """Test DatabaseConfig with mongo backend."""
        config = DatabaseConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_database_config_mongomock(self):
        """Test DatabaseConfig with mongomock backend."""
        config = DatabaseConfig(type="mongomock", prefix="wks", data={})
        assert config.type == "mongomock"
        assert config.prefix == "wks"

    def test_database_config_missing_prefix(self):
        """Test DatabaseConfig raises error when prefix is missing (config-first principle)."""
        with pytest.raises(ValidationError):
            DatabaseConfig(type="mongo", data={"uri": "mongodb://localhost:27017/"})

    def test_database_config_custom_prefix(self):
        """Test DatabaseConfig with custom prefix."""
        config = DatabaseConfig(type="mongo", prefix="custom", data={"uri": "mongodb://localhost:27017/"})
        assert config.prefix == "custom"

    def test_database_config_missing_type(self):
        """Test DatabaseConfig raises error when type is missing."""
        with pytest.raises(ValueError, match="database.type is required"):
            DatabaseConfig(prefix="wks", data={"uri": "mongodb://localhost:27017/"})

    def test_database_config_unknown_type(self):
        """Test DatabaseConfig raises error for unknown backend type."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            DatabaseConfig(type="invalid", prefix="wks", data={"uri": "mongodb://localhost:27017/"})

    def test_database_config_missing_data(self):
        """Test DatabaseConfig raises error when data is missing."""
        with pytest.raises(ValueError, match="database.data is required"):
            DatabaseConfig(type="mongo", prefix="wks")

    def test_database_config_mongomock_no_uri_required(self):
        """Test DatabaseConfig doesn't require uri for mongomock (in-memory database)."""
        # mongomock doesn't require any config data (empty dict is fine)
        config = DatabaseConfig(type="mongomock", prefix="wks", data={})
        assert config.type == "mongomock"
        # mongo requires uri, so empty dict should fail validation at backend level
        with pytest.raises(Exception):  # Will fail at _MongoDbConfigData validation
            DatabaseConfig(type="mongo", prefix="wks", data={})

    def test_database_config_invalid_mongo_uri(self):
        """Test DatabaseConfig validates mongo URI format."""
        # _MongoDbConfigData validates URI format
        with pytest.raises(Exception, match="must start with 'mongodb://'"):
            DatabaseConfig(type="mongo", prefix="wks", data={"uri": "invalid-uri"})

    def test_database_config_backend_registry(self):
        """Test that _BACKEND_REGISTRY contains expected backends."""
        # The registry is used internally by DatabaseConfig, test it works by creating configs
        mongo_config = DatabaseConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        assert mongo_config.type == "mongo"

        mongomock_config = DatabaseConfig(type="mongomock", prefix="wks", data={})
        assert mongomock_config.type == "mongomock"

        # Test unknown type fails
        with pytest.raises(ValueError, match="Unknown backend type"):
            DatabaseConfig(type="invalid", prefix="wks", data={})

    def test_database_config_from_dict(self):
        """Test DatabaseConfig can be created from dict."""
        config_dict = {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        config = DatabaseConfig(**config_dict)
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_database_config_model_validator_before(self):
        """Test model_validator intercepts and transforms data."""
        config_dict = {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        config = DatabaseConfig(**config_dict)
        # Verify data was transformed to _MongoDbConfigData instance
        assert hasattr(config.data, "uri")
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_database_config_model_validator_with_mongomock(self):
        """Test model_validator works with mongomock backend."""
        config_dict = {"type": "mongomock", "prefix": "wks", "data": {}}
        config = DatabaseConfig(**config_dict)
        # Verify data was transformed to _MongoMockDbConfigData instance
        assert config.type == "mongomock"
