"""Tests for wks/config.py - WKSConfig and related dataclasses."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from wks.config import (
    ConfigError,
    MongoSettings,
    MetricsConfig,
    DisplayConfig,
    WKSConfig,
    get_config_path,
    load_config,
    DEFAULT_MONGO_URI,
    DEFAULT_TIMESTAMP_FORMAT,
)


class TestMongoSettings:
    """Tests for MongoSettings dataclass."""

    def test_valid_uri(self):
        s = MongoSettings(uri="mongodb://localhost:27017/")
        assert s.uri == "mongodb://localhost:27017/"

    def test_valid_srv_uri(self):
        s = MongoSettings(uri="mongodb+srv://cluster.example.com/")
        assert s.uri == "mongodb+srv://cluster.example.com/"

    def test_empty_uri_uses_default(self):
        s = MongoSettings(uri="")
        assert s.uri == DEFAULT_MONGO_URI

    def test_invalid_uri_raises(self):
        with pytest.raises(ConfigError) as exc:
            MongoSettings(uri="http://localhost")
        assert "must start with 'mongodb://'" in str(exc.value)

    def test_from_config_with_uri(self):
        cfg = {"db": {"uri": "mongodb://custom:27017/"}}
        s = MongoSettings.from_config(cfg)
        assert s.uri == "mongodb://custom:27017/"

    def test_from_config_uses_default(self):
        s = MongoSettings.from_config({})
        assert s.uri == DEFAULT_MONGO_URI


class TestMetricsConfig:
    """Tests for MetricsConfig dataclass."""

    def test_defaults(self):
        m = MetricsConfig()
        assert m.fs_rate_short_window_secs == 10.0
        assert m.fs_rate_long_window_secs == 600.0
        assert m.fs_rate_short_weight == 0.8
        assert m.fs_rate_long_weight == 0.2

    def test_from_config_custom(self):
        cfg = {"metrics": {
            "fs_rate_short_window_secs": 5.0,
            "fs_rate_long_window_secs": 300.0,
        }}
        m = MetricsConfig.from_config(cfg)
        assert m.fs_rate_short_window_secs == 5.0
        assert m.fs_rate_long_window_secs == 300.0

    def test_from_config_empty(self):
        m = MetricsConfig.from_config({})
        assert m.fs_rate_short_window_secs == 10.0


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
                "database": "wks.monitor"
            },
            "vault": {
                "base_dir": str(tmp_path / "vault"),
                "database": "wks.vault"
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {}
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "_router": {
                    "rules": [],
                    "fallback": "myers",
                },
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        return config_path

    def test_load_valid(self, valid_config):
        cfg = WKSConfig.load(valid_config)
        assert cfg.monitor.database == "wks.monitor"
        assert cfg.vault.database == "wks.vault"
        assert cfg.mongo.uri == DEFAULT_MONGO_URI

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
                "database": "wks.monitor"
            },
            "vault": {
                "base_dir": str(tmp_path / "vault"),
                "database": "wks.vault"
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {}
            },
            "diff": {
                "engines": {
                    "myers": {"enabled": True, "is_default": True},
                },
                "_router": {
                    "rules": [],
                    "fallback": "myers",
                },
            }
        }
        (tmp_path / ".wks" / "config.json").write_text(json.dumps(config))
        
        # Call without path argument - should use default
        cfg = WKSConfig.load()
        assert cfg.monitor.database == "wks.monitor"


class TestGetConfigPath:
    """Tests for get_config_path()."""

    def test_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        path = get_config_path()
        assert path.name == "config.json"
        assert ".wks" in str(path)


class TestLoadConfig:
    """Tests for load_config() deprecated function."""

    def test_returns_dict(self, tmp_path):
        config = {
            "monitor": {
                "include_paths": ["~"],
                "exclude_paths": [],
                "include_dirnames": [],
                "exclude_dirnames": [],
                "include_globs": [],
                "exclude_globs": [],
                "managed_directories": {"~": 100},
                "database": "wks.monitor"
            },
            "vault": {
                "base_dir": str(tmp_path / "vault"),
                "database": "wks.vault"
            },
            "transform": {
                "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
                "engines": {}
            }
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))
        
        result = load_config(config_path)
        assert isinstance(result, dict)
        assert "monitor" in result
        assert "vault" in result

    def test_returns_empty_on_error(self, tmp_path):
        result = load_config(tmp_path / "nonexistent.json")
        assert result == {}

