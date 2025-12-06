"""Unit tests for wks.api.config.get_config_path module."""

from pathlib import Path

import pytest

from wks.api.config.get_config_path import get_config_path

pytestmark = pytest.mark.config


class TestGetConfigPath:
    """Test get_config_path function."""

    def test_get_config_path_returns_path(self, monkeypatch, tmp_path):
        """Test get_config_path() returns a Path."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        path = get_config_path()

        assert isinstance(path, Path)
        assert path.name == "config.json"

    def test_get_config_path_under_home_dir(self, monkeypatch, tmp_path):
        """Test get_config_path() returns path under home directory."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        path = get_config_path()

        assert path.parent == tmp_path.resolve()
        assert path == tmp_path.resolve() / "config.json"
