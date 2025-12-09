"""Unit tests for wks.api.config.WKSConfig module."""

import json
from unittest.mock import patch

import pytest

from pydantic import ValidationError

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.DatabaseConfig import DatabaseConfig
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.config


class TestWKSConfigLoad:
    """Test WKSConfig.load() method."""

    def test_load_valid_config(self, wks_home_with_priority):
        """Test load() with valid config file."""
        config = WKSConfig.load()

        assert isinstance(config, WKSConfig)
        assert isinstance(config.monitor, MonitorConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert config.monitor.database == "monitor"
        assert config.database.type == "mongomock"

    def test_load_uses_default_path(self, wks_home_with_priority):
        """Test load() uses get_config_path() to find config file."""
        config = WKSConfig.load()
        assert isinstance(config, WKSConfig)

    def test_load_file_not_found(self, tmp_path, monkeypatch):
        """Test load() raises ValueError when file doesn't exist."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        # Don't create config.json
        with pytest.raises(ValueError) as exc_info:
            WKSConfig.load()
        assert "not found" in str(exc_info.value).lower()

    def test_load_invalid_json(self, tmp_path, monkeypatch):
        """Test load() raises ValueError for invalid JSON."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        config_path = tmp_path / "config.json"
        config_path.write_text("{invalid json")
        with pytest.raises(ValueError) as exc_info:
            WKSConfig.load()
        assert "Invalid JSON" in str(exc_info.value)

    def test_load_missing_required_section(self, tmp_path, monkeypatch):
        """Test load() raises ValidationError when required section is missing."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")
        with pytest.raises(ValidationError):
            WKSConfig.load()


class TestWKSConfigPathMethods:
    """Test WKSConfig path-related methods."""

    def test_get_home_dir_with_env(self, tmp_path, monkeypatch):
        """Test get_home_dir() uses WKS_HOME environment variable."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        home_dir = WKSConfig.get_home_dir()
        assert home_dir == tmp_path.resolve()

    def test_get_home_dir_without_env(self, monkeypatch):
        """Test get_home_dir() defaults to ~/.wks when WKS_HOME not set."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        from pathlib import Path
        home_dir = WKSConfig.get_home_dir()
        assert home_dir == Path.home() / ".wks"

    def test_get_config_path(self, tmp_path, monkeypatch):
        """Test get_config_path() returns config.json in home directory."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        config_path = WKSConfig.get_config_path()
        assert config_path == tmp_path / "config.json"

    def test_path_property(self, wks_home_with_priority):
        """Test path property returns config path."""
        config = WKSConfig.load()
        assert config.path == wks_home_with_priority / "config.json"


class TestWKSConfigToDict:
    """Test WKSConfig.to_dict() method."""

    def test_to_dict_returns_dict(self, wks_home_with_priority):
        """Test to_dict() returns a dictionary."""
        config = WKSConfig.load()
        result = config.to_dict()

        assert isinstance(result, dict)
        assert "monitor" in result
        assert "database" in result
        assert "daemon" in result

    def test_to_dict_includes_monitor(self, wks_home_with_priority):
        """Test to_dict() includes monitor config."""
        config = WKSConfig.load()
        result = config.to_dict()

        assert "monitor" in result
        assert isinstance(result["monitor"], dict)
        assert result["monitor"]["database"] == "monitor"


class TestWKSConfigSave:
    """Test WKSConfig.save() method."""

    def test_save_writes_file(self, wks_home_with_priority):
        """Test save() writes config to file."""
        config = WKSConfig.load()
        config_path = wks_home_with_priority / "config.json"
        config.save()

        assert config_path.exists()
        loaded = json.loads(config_path.read_text())
        assert "monitor" in loaded

    def test_save_uses_default_path(self, wks_home_with_priority):
        """Test save() uses get_config_path() to save config file."""
        config = WKSConfig.load()
        config_path = wks_home_with_priority / "config.json"
        config.save()

        assert config_path.exists()
        loaded = json.loads(config_path.read_text())
        assert "monitor" in loaded

    def test_save_atomic_write(self, wks_home_with_priority):
        """Test save() uses atomic write (temp file then rename)."""
        config = WKSConfig.load()
        config_path = wks_home_with_priority / "config.json"
        config.save()

        # Temp file should not exist after successful save
        temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
        assert not temp_path.exists()
        assert config_path.exists()

    def test_save_cleans_up_temp_on_error(self, wks_home_with_priority):
        """Test save() cleans up temp file on error."""
        config = WKSConfig.load()
        config_path = wks_home_with_priority / "config.json"
        temp_path = config_path.with_suffix(config_path.suffix + ".tmp")

        # Make the directory read-only to cause an error
        config_path.parent.chmod(0o444)
        try:
            with pytest.raises(RuntimeError):
                config.save()
        finally:
            config_path.parent.chmod(0o755)

        # Temp file should be cleaned up
        assert not temp_path.exists()

    def test_save_cleans_up_temp_on_error_when_temp_exists(self, wks_home_with_priority):
        """Test save() cleans up temp file on error when temp file exists."""
        config = WKSConfig.load()
        config_path = wks_home_with_priority / "config.json"
        temp_path = config_path.with_suffix(config_path.suffix + ".tmp")

        # Mock json.dump to raise an exception
        with patch("json.dump", side_effect=OSError("Simulated write error")):
            # Create temp file first to simulate it existing when error occurs
            temp_path.write_text("temp")
            assert temp_path.exists()

            with pytest.raises(RuntimeError):
                config.save()

        # Temp file should be cleaned up
        assert not temp_path.exists()
