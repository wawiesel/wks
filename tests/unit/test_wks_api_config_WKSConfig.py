"""Unit tests for wks.api.config.WKSConfig module."""

import json
from unittest.mock import patch

import pytest

from wks.api.config.ConfigError import ConfigError
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.DbConfig import DbConfig
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.config


def build_valid_config_dict(tmp_path) -> dict:
    """Build a valid config dict for testing."""
    return {
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
        "database": {
            "type": "mongo",
            "prefix": "wks",
            "data": {"uri": "mongodb://localhost:27017/"},
        },
        "transform": {
            "cache": {"location": ".wks/cache", "max_size_bytes": 1000000},
            "engines": {},
            "database": "transform",
        },
    }


class TestWKSConfigLoad:
    """Test WKSConfig.load() method."""

    def test_load_valid_config(self, tmp_path):
        """Test load() with valid config file."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)

        assert isinstance(config, WKSConfig)
        assert isinstance(config.monitor, MonitorConfig)
        assert isinstance(config.database, DbConfig)
        assert config.monitor.database == "monitor"
        assert config.database.type == "mongo"

    def test_load_uses_default_path(self, tmp_path, monkeypatch):
        """Test load() without path argument uses get_config_path()."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        with patch("wks.api.config.get_config_path.get_config_path", return_value=config_path):
            config = WKSConfig.load()
            assert isinstance(config, WKSConfig)

    def test_load_file_not_found(self, tmp_path):
        """Test load() raises ConfigError when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.json"
        with pytest.raises(ConfigError) as exc_info:
            WKSConfig.load(nonexistent)
        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_json(self, tmp_path):
        """Test load() raises ConfigError for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")
        with pytest.raises(ConfigError) as exc_info:
            WKSConfig.load(bad_file)
        assert "Invalid JSON" in str(exc_info.value)

    def test_load_missing_required_section(self, tmp_path):
        """Test load() raises ConfigError when required section is missing."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        with pytest.raises(ConfigError) as exc_info:
            WKSConfig.load(config_path)
        assert "validation failed" in str(exc_info.value).lower()

    def test_load_with_diff_section(self, tmp_path):
        """Test load() handles optional diff section."""
        config_dict = build_valid_config_dict(tmp_path)
        config_dict["diff"] = {
            "engines": {
                "myers": {"enabled": True, "is_default": True},
            },
            "router": {
                "rules": [],
                "fallback": "myers",
            },
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        assert config.diff is not None

    def test_load_without_diff_section(self, tmp_path):
        """Test load() handles missing diff section."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        assert config.diff is None


class TestWKSConfigToDict:
    """Test WKSConfig.to_dict() method."""

    def test_to_dict_returns_dict(self, tmp_path):
        """Test to_dict() returns a dictionary."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        result = config.to_dict()

        assert isinstance(result, dict)
        assert "monitor" in result
        assert "vault" in result
        assert "database" in result

    def test_to_dict_includes_monitor(self, tmp_path):
        """Test to_dict() includes monitor config."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        result = config.to_dict()

        assert "monitor" in result
        assert isinstance(result["monitor"], dict)
        assert result["monitor"]["database"] == "monitor"


class TestWKSConfigSave:
    """Test WKSConfig.save() method."""

    def test_save_writes_file(self, tmp_path):
        """Test save() writes config to file."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        save_path = tmp_path / "saved.json"
        config.save(save_path)

        assert save_path.exists()
        loaded = json.loads(save_path.read_text())
        assert "monitor" in loaded

    def test_save_uses_default_path(self, tmp_path, monkeypatch):
        """Test save() without path uses get_config_path()."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        default_path = tmp_path / "config.json"

        with patch("wks.api.config.get_config_path.get_config_path", return_value=default_path):
            config.save()
            assert default_path.exists()

    def test_save_atomic_write(self, tmp_path):
        """Test save() uses atomic write (temp file then rename)."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        save_path = tmp_path / "saved.json"
        config.save(save_path)

        # Temp file should not exist after successful save
        temp_path = save_path.with_suffix(save_path.suffix + ".tmp")
        assert not temp_path.exists()
        assert save_path.exists()

    def test_save_cleans_up_temp_on_error(self, tmp_path):
        """Test save() cleans up temp file on error."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        save_path = tmp_path / "saved.json"

        # Make the directory read-only to cause an error
        save_path.parent.chmod(0o444)
        try:
            with pytest.raises(Exception):
                config.save(save_path)
        finally:
            save_path.parent.chmod(0o755)

        # Temp file should be cleaned up
        temp_path = save_path.with_suffix(save_path.suffix + ".tmp")
        assert not temp_path.exists()

    def test_save_cleans_up_temp_on_error_when_temp_exists(self, tmp_path, monkeypatch):
        """Test save() cleans up temp file on error when temp file exists."""
        config_dict = build_valid_config_dict(tmp_path)
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config_dict))

        config = WKSConfig.load(config_path)
        save_path = tmp_path / "saved.json"
        temp_path = save_path.with_suffix(save_path.suffix + ".tmp")

        # Mock json.dump to raise an exception
        with patch("json.dump", side_effect=OSError("Simulated write error")):
            # Create temp file first to simulate it existing when error occurs
            temp_path.write_text("temp")
            assert temp_path.exists()

            with pytest.raises(Exception):
                config.save(save_path)

        # Temp file should be cleaned up (line 121 - the unlink in exception handler)
        assert not temp_path.exists()
