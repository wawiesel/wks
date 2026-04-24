import pytest
from pydantic import ValidationError

from wks.api.database.DatabaseConfig import DatabaseConfig

pytestmark = pytest.mark.database


class TestDatabaseConfig:
    def test_database_config_mongo(self):
        config = DatabaseConfig.model_validate(
            {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        )
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"  # type: ignore[attr-defined]
        assert config.data.local is False  # type: ignore[attr-defined]

    def test_database_config_mongomock(self):
        config = DatabaseConfig.model_validate({"type": "mongomock", "prefix": "wks", "data": {}})
        assert config.type == "mongomock"
        assert config.prefix == "wks"

    def test_database_config_missing_prefix(self):
        with pytest.raises(ValidationError):
            DatabaseConfig.model_validate({"type": "mongo", "data": {"uri": "mongodb://localhost/"}})

    def test_database_config_custom_prefix(self):
        config = DatabaseConfig.model_validate(
            {
                "type": "mongo",
                "prefix": "custom",
                "prune_frequency_secs": 3600,
                "data": {"uri": "mongodb://localhost:27017/"},
            }
        )
        assert config.prefix == "custom"

    def test_database_config_invalid_data_type(self):
        with pytest.raises(ValueError, match="database config must be a dict"):
            DatabaseConfig.model_validate("invalid")

    def test_database_config_missing_type(self):
        with pytest.raises(ValueError, match=r"database\.type is required"):
            DatabaseConfig.model_validate({"data": {}, "prefix": "wks"})

    def test_database_config_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown backend type"):
            DatabaseConfig.model_validate(
                {"type": "invalid", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
            )

    def test_database_config_missing_data(self):
        with pytest.raises(ValueError, match=r"database\.data is required"):
            DatabaseConfig.model_validate({"type": "mongo", "prefix": "wks"})

    def test_database_config_mongomock_no_uri_required(self):
        config = DatabaseConfig.model_validate({"type": "mongomock", "prefix": "wks", "data": {}})
        assert config.type == "mongomock"
        with pytest.raises(ValidationError):
            DatabaseConfig.model_validate({"type": "mongo", "prefix": "wks", "data": {}})

    def test_database_config_invalid_mongo_uri(self):
        with pytest.raises(Exception, match="must start with 'mongodb://'"):
            DatabaseConfig.model_validate({"type": "mongo", "prefix": "wks", "data": {"uri": "invalid-uri"}})

    def test_database_config_mongo_local_requires_port(self):
        cfg = DatabaseConfig.model_validate(
            {
                "type": "mongo",
                "prefix": "wks",
                "data": {
                    "uri": "mongodb://127.0.0.1:27017/",
                    "local": True,
                },
                "prune_frequency_secs": 3600,
            }
        )
        assert cfg.data.local is True  # type: ignore[attr-defined]

    def test_database_config_from_dict(self):
        config_dict = {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        config = DatabaseConfig.model_validate(config_dict)
        assert config.type == "mongo"
        assert config.prefix == "wks"
        assert config.data.uri == "mongodb://localhost:27017/"  # type: ignore[attr-defined]

    def test_database_config_model_validator_before(self):
        config_dict = {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        config = DatabaseConfig.model_validate(config_dict)
        assert hasattr(config.data, "uri")
        assert config.data.uri == "mongodb://localhost:27017/"  # type: ignore[attr-defined]

    def test_database_config_model_validator_with_mongomock(self):
        config_dict = {"type": "mongomock", "prefix": "wks", "prune_frequency_secs": 3600, "data": {}}
        config = DatabaseConfig.model_validate(config_dict)
        assert config.type == "mongomock"

    def test_database_config_requires_dict(self):
        with pytest.raises(ValueError, match="database config must be a dict"):
            DatabaseConfig.model_validate("not a dict")

    def test_mongo_data_requires_uri(self):
        with pytest.raises(Exception, match="must start with 'mongodb://'"):
            DatabaseConfig.model_validate({"type": "mongo", "prefix": "wks", "data": {"uri": ""}})

    def test_database_config_model_dump_serializes_data(self):
        cfg = DatabaseConfig.model_validate(
            {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}}
        )
        dumped = cfg.model_dump(mode="python")
        assert dumped["type"] == "mongo"
        assert dumped["prefix"] == "wks"
        assert isinstance(dumped["data"], dict)
        assert dumped["data"]["uri"] == "mongodb://localhost:27017/"
