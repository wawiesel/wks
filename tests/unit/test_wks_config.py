"""Tests for wks/config.py - WKSConfig and related dataclasses."""

import json

import pytest

from wks.config import (
    DEFAULT_MONGO_URI,
    DEFAULT_TIMESTAMP_FORMAT,
    ConfigError,
    DisplayConfig,
    MetricsConfig,
    WKSConfig,
    get_config_path,
)
from wks.api.db._mongo.MongoDbConfig import MongoDbConfig


@pytest.mark.unit
class TestMongoDbConfig:
    """Tests for MongoDbConfig dataclass."""

    def test_valid_mongo_config(self):
        s = MongoDbConfig(uri="mongodb://localhost:27017/")
        assert s.uri == "mongodb://localhost:27017/"

    def test_valid_srv_uri(self):
        s = MongoDbConfig(uri="mongodb+srv://cluster.example.com/")
        assert s.uri == "mongodb+srv://cluster.example.com/"

    def test_missing_uri_raises(self):
        with pytest.raises(ConfigError) as exc:
            MongoDbConfig(uri="")
        assert "db.uri is required when db.type is 'mongo'" in str(exc.value)

    def test_invalid_uri_raises(self):
        with pytest.raises(ConfigError) as exc:
            MongoDbConfig(uri="http://localhost")
        assert "must start with 'mongodb://'" in str(exc.value)

    def test_from_config_with_uri(self):
        cfg = {"db": {"type": "mongo", "uri": "mongodb://custom:27017/"}}
        s = MongoDbConfig.from_config(cfg)
        assert s.uri == "mongodb://custom:27017/"

    def test_from_config_missing_uri_raises(self):
        with pytest.raises(ConfigError) as exc:
            MongoDbConfig.from_config({"db": {"type": "mongo"}})
        assert "db.uri is required when db.type is 'mongo'" in str(exc.value)


@pytest.mark.unit
class TestDbConfigLoading:
    """Tests for DbConfig loading via WKSConfig.load()."""

    def test_load_mongo_config(self, tmp_path):
        """Test that WKSConfig.load() creates MongoDbConfig when type='mongo'."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor",
            },
            "vault": {"base_dir": str(tmp_path / "vault"), "database": "wks.vault"},
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
            },
            "db": {"type": "mongo", "uri": "mongodb://custom:27017/"},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        
        cfg = WKSConfig.load(config_path)
        assert isinstance(cfg.db, MongoDbConfig)
        assert cfg.db.uri == "mongodb://custom:27017/"

    def test_load_missing_type_raises(self, tmp_path):
        """Test that missing db.type raises ConfigError."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor",
            },
            "vault": {"base_dir": str(tmp_path / "vault"), "database": "wks.vault"},
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
            },
            "db": {"uri": "mongodb://localhost:27017/"},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        
        with pytest.raises(ConfigError) as exc:
            WKSConfig.load(config_path)
        assert "db.type is required" in str(exc.value)

    def test_load_unknown_type_raises(self, tmp_path):
        """Test that unknown db.type raises ConfigError."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor",
            },
            "vault": {"base_dir": str(tmp_path / "vault"), "database": "wks.vault"},
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
            },
            "db": {"type": "postgres", "uri": "postgres://localhost"},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        
        with pytest.raises(ConfigError) as exc:
            WKSConfig.load(config_path)
        assert "Unknown db.type" in str(exc.value)


@pytest.mark.unit
class TestMetricsConfig:
    """Tests for MetricsConfig dataclass."""

    def test_defaults(self):
        m = MetricsConfig()
        assert m.fs_rate_short_window_secs == 10.0
        assert m.fs_rate_long_window_secs == 600.0
        assert m.fs_rate_short_weight == 0.8
        assert m.fs_rate_long_weight == 0.2

    def test_from_config_custom(self):
        cfg = {
            "metrics": {
                "fs_rate_short_window_secs": 5.0,
                "fs_rate_long_window_secs": 300.0,
            }
        }
        m = MetricsConfig.from_config(cfg)
        assert m.fs_rate_short_window_secs == 5.0
        assert m.fs_rate_long_window_secs == 300.0

    def test_from_config_empty(self):
        m = MetricsConfig.from_config({})
        assert m.fs_rate_short_window_secs == 10.0


@pytest.mark.unit
class TestDisplayConfig:
    """Tests for DisplayConfig dataclass."""

    def test_defaults(self):
        d = DisplayConfig()
        assert d.timestamp_format == DEFAULT_TIMESTAMP_FORMAT

    def test_from_config_custom(self):
        cfg = {"display": {"timestamp_format": "%H:%M:%S"}}
        d = DisplayConfig.from_config(cfg)
        assert d.timestamp_format == "%H:%M:%S"

    def test_from_config_empty(self):
        d = DisplayConfig.from_config({})
        assert d.timestamp_format == DEFAULT_TIMESTAMP_FORMAT


@pytest.mark.unit
class TestWKSConfig:
    """Tests for WKSConfig.load()."""

    @pytest.fixture
    def valid_config(self, tmp_path):
        """Create a valid config file."""
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor",
            },
            "vault": {"base_dir": str(tmp_path / "vault"), "database": "wks.vault"},
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "_router": {
                    "rules": [],
                    "fallback": "myers",
                },
            },
            "db": {
                "type": "mongo",
                "uri": "mongodb://localhost:27017/"
            },
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        return config_path

    def test_load_valid(self, valid_config):
        cfg = WKSConfig.load(valid_config)
        assert cfg.monitor.database == "wks.monitor"
        assert cfg.vault.database == "wks.vault"
        assert isinstance(cfg.db, MongoDbConfig)
        assert cfg.db.uri == "mongodb://localhost:27017/"

    def test_load_file_not_found(self, tmp_path):
        with pytest.raises(ConfigError) as exc:
            WKSConfig.load(tmp_path / "nonexistent.json")
        assert "not found" in str(exc.value)

    def test_load_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")
        with pytest.raises(ConfigError) as exc:
            WKSConfig.load(bad_file)
        assert "Invalid JSON" in str(exc.value)

    def test_load_missing_required_section(self, tmp_path):
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        with pytest.raises(ConfigError) as exc:
            WKSConfig.load(config_path)
        assert "validation failed" in str(exc.value).lower()

    def test_load_uses_default_path(self, tmp_path, monkeypatch):
        """Test that load() with no arg uses get_config_path()."""
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".wks").mkdir()
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor",
            },
            "vault": {"base_dir": str(tmp_path / "vault"), "database": "wks.vault"},
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "_router": {
                    "rules": [],
                    "fallback": "myers",
                },
            },
            "db": {
                "type": "mongo",
                "uri": "mongodb://localhost:27017/"
            },
        }
        (tmp_path / ".wks" / "config.json").write_text(json.dumps(config))

        # Call without path argument - should use default
        cfg = WKSConfig.load()
        assert cfg.monitor.database == "wks.monitor"


@pytest.mark.unit
class TestGetConfigPath:
    """Tests for get_config_path()."""

    def test_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        path = get_config_path()
        assert path.name == "config.json"
        assert ".wks" in str(path)
