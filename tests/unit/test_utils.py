"""Tests for utility functions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from wks.utils import (
    expand_path,
    file_checksum,
    get_package_version,
    get_wks_home,
    wks_home_path,
)


@pytest.mark.unit
class TestFileChecksum:
    """Test file_checksum function."""

    def test_file_checksum(self, tmp_path):
        """Test file_checksum calculates SHA256."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        checksum = file_checksum(test_file)

        assert len(checksum) == 64  # SHA256 hex digest length
        assert isinstance(checksum, str)

    def test_file_checksum_empty_file(self, tmp_path):
        """Test file_checksum with empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        checksum = file_checksum(test_file)

        assert len(checksum) == 64
        # Empty file has known SHA256
        assert checksum == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_file_checksum_large_file(self, tmp_path):
        """Test file_checksum with large file (tests chunk reading)."""
        test_file = tmp_path / "large.txt"
        # Write 2MB of data
        test_file.write_bytes(b"x" * (2 * 1024 * 1024))

        checksum = file_checksum(test_file)

        assert len(checksum) == 64


@pytest.mark.unit
class TestGetPackageVersion:
    """Test get_package_version function."""

    def test_get_package_version(self):
        """Test get_package_version returns version."""
        version = get_package_version()
        assert isinstance(version, str)
        assert version in ("unknown", "0.0.0", "0.1.0") or len(version) > 0

    @patch("wks.utils.importlib_metadata.version")
    @patch("wks.utils._VERSION_CACHE", None)
    def test_get_package_version_exception(self, mock_version):
        """Test get_package_version handles exception."""
        mock_version.side_effect = Exception("Not found")

        # Clear cache first
        import wks.utils

        wks.utils._VERSION_CACHE = None

        version = get_package_version()

        assert version == "unknown"

    def test_get_package_version_cached(self):
        """Test get_package_version is cached."""
        version1 = get_package_version()
        version2 = get_package_version()

        assert version1 == version2


@pytest.mark.unit
class TestExpandPath:
    """Test expand_path function."""

    def test_expand_path_absolute(self):
        """Test expand_path with absolute path."""
        path = expand_path("/absolute/path")
        assert isinstance(path, Path)
        assert str(path) == "/absolute/path"

    def test_expand_path_home(self):
        """Test expand_path with ~."""
        path = expand_path("~/test")
        assert isinstance(path, Path)
        assert "~" not in str(path)


@pytest.mark.unit
class TestGetWksHome:
    """Test get_wks_home function."""

    def test_get_wks_home_default(self, monkeypatch):
        """Test get_wks_home uses default when env vars not set."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        wks_home = get_wks_home()

        assert isinstance(wks_home, Path)
        assert wks_home.name == ".wks"

    def test_get_wks_home_env_var(self, monkeypatch, tmp_path):
        """Test get_wks_home uses WKS_HOME environment variable."""
        custom_home = tmp_path / "custom_wks"
        monkeypatch.setenv("WKS_HOME", str(custom_home))
        monkeypatch.delenv("HOME", raising=False)

        wks_home = get_wks_home()

        assert wks_home == custom_home.resolve()

    def test_get_wks_home_home_env(self, monkeypatch, tmp_path):
        """Test get_wks_home uses HOME environment variable."""
        custom_home = tmp_path / "custom_home"
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.setenv("HOME", str(custom_home))

        wks_home = get_wks_home()

        assert wks_home == custom_home / ".wks"

    def test_get_wks_home_precedence(self, monkeypatch, tmp_path):
        """Test WKS_HOME takes precedence over HOME."""
        wks_home_custom = tmp_path / "wks_custom"
        home_custom = tmp_path / "home_custom"
        monkeypatch.setenv("WKS_HOME", str(wks_home_custom))
        monkeypatch.setenv("HOME", str(home_custom))

        wks_home = get_wks_home()

        assert wks_home == wks_home_custom.resolve()


@pytest.mark.unit
class TestWksHomePath:
    """Test wks_home_path function."""

    def test_wks_home_path_no_parts(self, monkeypatch):
        """Test wks_home_path with no parts."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        path = wks_home_path()

        assert isinstance(path, Path)
        assert path.name == ".wks"

    def test_wks_home_path_with_parts(self, monkeypatch):
        """Test wks_home_path with parts."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        path = wks_home_path("config.json")

        assert isinstance(path, Path)
        assert path.name == "config.json"
        assert path.parent.name == ".wks"

    def test_wks_home_path_multiple_parts(self, monkeypatch):
        """Test wks_home_path with multiple parts."""
        monkeypatch.delenv("WKS_HOME", raising=False)
        monkeypatch.delenv("HOME", raising=False)

        path = wks_home_path("mongodb", "data")

        assert isinstance(path, Path)
        assert path.parts[-1] == "data"
        assert path.parts[-2] == "mongodb"
