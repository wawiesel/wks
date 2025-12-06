"""Tests for wks/config.py - WKSConfig and related dataclasses."""

import json

import pytest

from wks.api.config.ConfigError import ConfigError
from wks.api.config.DisplayConfig import DEFAULT_TIMESTAMP_FORMAT, DisplayConfig
from wks.api.config.get_config_path import get_config_path
from wks.api.config.MetricsConfig import MetricsConfig
from wks.api.config.WKSConfig import WKSConfig
from wks.api.db.DbConfig import DbConfig

# Note: MongoDbConfig tests removed - now using DbConfig with backend-specific data
# See test_wks_api_db_DbConfig.py for DbConfig tests


@pytest.mark.unit
class TestDbConfigLoading:
    """Tests for DbConfig loading via WKSConfig.load()."""

    def test_load_mongo_config(self, tmp_path):
        """Test that WKSConfig.load() creates DbConfig when type='mongo'."""
        config = {
            "monitor": {
                "filter": {
                    "include_paths": ["~"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {
                    "dirs": {"~": 100.0},
                    "weights": {},
                },
                "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
            },
            "vault": {
                "vault_type": "obsidian",
                "base_dir": str(tmp_path / "vault"),
                "wks_dir": "WKS",
                "update_frequency_seconds": 3600.0,
                "database": "vault",
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
                "database": "transform",
            },
            "db": {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://custom:27017/"}},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        cfg = WKSConfig.load(config_path)
        assert isinstance(cfg.db, DbConfig)
        assert cfg.db.type == "mongo"
        assert cfg.db.data.uri == "mongodb://custom:27017/"

    def test_load_missing_type_raises(self, tmp_path):
        """Test that missing db.type raises ConfigError."""
        config = {
            "monitor": {
                "filter": {
                    "include_paths": ["~"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {"dirs": {"~": 100.0}, "weights": {}},
                "database": "monitor",
                "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
            },
            "vault": {
                "vault_type": "obsidian",
                "base_dir": str(tmp_path / "vault"),
                "wks_dir": "WKS",
                "update_frequency_seconds": 3600.0,
                "database": "vault",
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
                "database": "transform",
            },
            "db": {"prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        with pytest.raises(ValueError) as exc:
            WKSConfig.load(config_path)
        assert "db.type is required" in str(exc.value)

    def test_load_unknown_type_raises(self, tmp_path):
        """Test that unknown db.type raises ConfigError."""
        config = {
            "monitor": {
                "filter": {
                    "include_paths": ["~"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {"dirs": {"~": 100.0}, "weights": {}},
                "database": "monitor",
                "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
            },
            "vault": {
                "vault_type": "obsidian",
                "base_dir": str(tmp_path / "vault"),
                "wks_dir": "WKS",
                "update_frequency_seconds": 3600.0,
                "database": "vault",
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
                "database": "transform",
            },
            "db": {"type": "postgres", "prefix": "wks", "data": {}},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        with pytest.raises(ValueError) as exc:
            WKSConfig.load(config_path)
        assert "Unknown backend type" in str(exc.value)


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
                "filter": {
                    "include_paths": ["~"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {"dirs": {"~": 100.0}, "weights": {}},
                "database": "monitor",
                "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
            },
            "vault": {
                "vault_type": "obsidian",
                "base_dir": str(tmp_path / "vault"),
                "wks_dir": "WKS",
                "update_frequency_seconds": 3600.0,
                "database": "vault",
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
                "database": "transform",
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "router": {
                    "rules": [],
                    "fallback": "myers",
                },
            },
            "db": {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        return config_path

    def test_load_valid(self, valid_config):
        cfg = WKSConfig.load(valid_config)
        assert cfg.monitor.database == "monitor"
        assert cfg.vault.database == "vault"
        assert isinstance(cfg.db, DbConfig)
        assert cfg.db.type == "mongo"
        assert cfg.db.data.uri == "mongodb://localhost:27017/"

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
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)
        (tmp_path).mkdir()
        config = {
            "monitor": {
                "filter": {
                    "include_paths": ["~"],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {"dirs": {"~": 100.0}, "weights": {}},
                "database": "monitor",
                "sync": {"max_documents": 1000000, "min_priority": 0.0, "prune_interval_secs": 300.0},
            },
            "vault": {
                "vault_type": "obsidian",
                "base_dir": str(tmp_path / "vault"),
                "wks_dir": "WKS",
                "update_frequency_seconds": 3600.0,
                "database": "vault",
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {},
                "database": "transform",
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "router": {
                    "rules": [],
                    "fallback": "myers",
                },
            },
            "db": {"type": "mongo", "prefix": "wks", "data": {"uri": "mongodb://localhost:27017/"}},
        }
        (tmp_path / "config.json").write_text(json.dumps(config))

        # Call without path argument - should use default
        cfg = WKSConfig.load()
        assert cfg.monitor.database == "monitor"


@pytest.mark.unit
class TestGetConfigPath:
    """Tests for get_config_path()."""

    def test_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        path = get_config_path()
        assert path.name == "config.json"
        assert ".wks" in str(path)
