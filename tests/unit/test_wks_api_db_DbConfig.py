"""Unit tests for wks.api.db.DbConfig module."""

import pytest
from pydantic import ValidationError

from wks.api.db.DbConfig import DbConfig

pytestmark = pytest.mark.db


class TestDbConfig:
    """Test DbConfig class."""

    def test_db_config_mongo(self):
        """Test DbConfig with mongo backend."""
        config = DbConfig(
            type="mongo",
            prefix="wks",
            data={"uri": "mongodb://localhost:27017/"}
        )
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_db_config_mongomock(self):
        """Test DbConfig with mongomock backend."""
        config = DbConfig(
            type="mongomock",
            prefix="wks",
            data={}
        )
        assert config.type == "mongomock"
        assert config.prefix == "wks"

    def test_db_config_missing_prefix(self):
        """Test DbConfig raises error when prefix is missing (config-first principle)."""
        with pytest.raises(ValidationError):
            DbConfig(
                type="mongo",
                data={"uri": "mongodb://localhost:27017/"}
            )

    def test_db_config_custom_prefix(self):
        """Test DbConfig with custom prefix."""
        config = DbConfig(
            type="mongo",
            prefix="custom",
            data={"uri": "mongodb://localhost:27017/"}
        )
        assert config.prefix == "custom"

    def test_db_config_missing_type(self):
        """Test DbConfig raises error when type is missing."""
        with pytest.raises(ValueError, match="db.type is required"):
            DbConfig(prefix="wks", data={"uri": "mongodb://localhost:27017/"})

    def test_db_config_unknown_type(self):
        """Test DbConfig raises error for unknown backend type."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            DbConfig(
                type="invalid",
                prefix="wks",
                data={"uri": "mongodb://localhost:27017/"}
            )

    def test_db_config_missing_data(self):
        """Test DbConfig raises error when data is missing."""
        with pytest.raises(ValueError, match="db.data is required"):
            DbConfig(type="mongo", prefix="wks")

    def test_db_config_empty_data(self):
        """Test DbConfig allows empty data dict (backend can have defaults)."""
        # mongomock allows empty dict (has default URI)
        config = DbConfig(type="mongomock", prefix="wks", data={})
        assert config.type == "mongomock"
        # mongo requires uri, so empty dict should fail validation at backend level
        with pytest.raises(Exception):  # Will fail at _MongoDbConfigData validation
            DbConfig(type="mongo", prefix="wks", data={})

    def test_db_config_invalid_mongo_uri(self):
        """Test DbConfig validates mongo URI format."""
        # _MongoDbConfigData validates URI format
        with pytest.raises(Exception, match="must start with 'mongodb://'"):
            DbConfig(
                type="mongo",
                prefix="wks",
                data={"uri": "invalid-uri"}
            )

    def test_db_config_backend_registry(self):
        """Test that _BACKEND_REGISTRY contains expected backends."""
        # The registry is used internally by DbConfig, test it works by creating configs
        mongo_config = DbConfig(type="mongo", prefix="wks", data={"uri": "mongodb://localhost:27017/"})
        assert mongo_config.type == "mongo"

        mongomock_config = DbConfig(type="mongomock", prefix="wks", data={})
        assert mongomock_config.type == "mongomock"

        # Test unknown type fails
        with pytest.raises(ValueError, match="Unknown backend type"):
            DbConfig(type="invalid", prefix="wks", data={})

    def test_db_config_from_dict(self):
        """Test DbConfig can be created from dict."""
        config_dict = {
            "type": "mongo",
            "prefix": "wks",
            "data": {"uri": "mongodb://localhost:27017/"}
        }
        config = DbConfig(**config_dict)
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_db_config_model_validator_before(self):
        """Test model_validator intercepts and transforms data."""
        config_dict = {
            "type": "mongo",
            "prefix": "wks",
            "data": {"uri": "mongodb://localhost:27017/"}
        }
        config = DbConfig(**config_dict)
        # Verify data was transformed to _MongoDbConfigData instance
        assert hasattr(config.data, 'uri')
        assert config.data.uri == "mongodb://localhost:27017/"

    def test_db_config_model_validator_with_mongomock(self):
        """Test model_validator works with mongomock backend."""
        config_dict = {
            "type": "mongomock",
            "prefix": "wks",
            "data": {}
        }
        config = DbConfig(**config_dict)
        # Verify data was transformed to _MongoMockDbConfigData instance
        assert config.type == "mongomock"
