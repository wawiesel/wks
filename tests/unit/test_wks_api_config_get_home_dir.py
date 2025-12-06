"""Unit tests for wks.api.config.get_home_dir module."""

from pathlib import Path

import pytest

from wks.api.config.get_home_dir import get_home_dir

pytestmark = pytest.mark.config


class TestGetHomeDir:
    """Test get_home_dir function."""

    def test_get_home_dir_no_args_default(self, monkeypatch):
        """Test get_home_dir() with no args uses default when env vars not set."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        home_dir = get_home_dir()

        assert isinstance(home_dir, Path)
        assert home_dir.name == ".wks"

    def test_get_home_dir_with_wks_home_env(self, monkeypatch, tmp_path):
        """Test get_home_dir() uses WKS_HOME environment variable."""
        custom_home = tmp_path / "custom_wks"
        monkeypatch.setenv("WKS_HOME", str(custom_home))
        monkeypatch.delenv("HOME", raising=False)

        home_dir = get_home_dir()

        assert home_dir == custom_home.resolve()

    def test_get_home_dir_with_home_env(self, monkeypatch, tmp_path):
        """Test get_home_dir() uses HOME environment variable."""
        custom_home = tmp_path / "custom_home"
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.setenv("HOME", str(custom_home))

        home_dir = get_home_dir()

        assert home_dir == custom_home / ".wks"

    def test_get_home_dir_precedence(self, monkeypatch, tmp_path):
        """Test WKS_HOME takes precedence over HOME."""
        wks_home_custom = tmp_path / "wks_custom"
        home_custom = tmp_path / "home_custom"
        monkeypatch.setenv("WKS_HOME", str(wks_home_custom))
        monkeypatch.setenv("HOME", str(home_custom))

        home_dir = get_home_dir()

        assert home_dir == wks_home_custom.resolve()

    def test_get_home_dir_with_single_part(self, monkeypatch, tmp_path):
        """Test get_home_dir() with single part."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        path = get_home_dir("config.json")

        assert isinstance(path, Path)
        assert path.name == "config.json"
        assert path.parent == tmp_path.resolve()

    def test_get_home_dir_with_multiple_parts(self, monkeypatch, tmp_path):
        """Test get_home_dir() with multiple parts."""
        monkeypatch.setenv("WKS_HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        path = get_home_dir("mongodb", "data")

        assert isinstance(path, Path)
        assert path.parts[-1] == "data"
        assert path.parts[-2] == "mongodb"
        assert path.parent.parent == tmp_path.resolve()

    def test_get_home_dir_expands_user(self, monkeypatch, tmp_path):
        """Test get_home_dir() expands ~ in WKS_HOME."""
        custom_home = tmp_path / "custom_wks"
        monkeypatch.setenv("WKS_HOME", f"~/{custom_home.name}")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        home_dir = get_home_dir()

        # Should expand ~ to actual home
        assert isinstance(home_dir, Path)
        assert home_dir.is_absolute()
