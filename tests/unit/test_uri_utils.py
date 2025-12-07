"""Tests for URI utility functions."""

from pathlib import Path

import pytest

from wks.utils.uri_utils import convert_to_uri, path_to_uri, uri_to_path


@pytest.mark.unit
class TestPathToUri:
    """Test path_to_uri function."""

    def test_path_to_uri(self, tmp_path):
        """Test path_to_uri converts Path to file:// URI."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        uri = path_to_uri(test_file)

        assert uri.startswith("file://")
        assert "test.txt" in uri

    def test_path_to_uri_resolves(self, tmp_path):
        """Test path_to_uri resolves relative paths."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Use relative path
        relative_path = Path(test_file.name)
        uri = path_to_uri(relative_path)

        assert uri.startswith("file://")
        assert uri.endswith("test.txt")


@pytest.mark.unit
class TestUriToPath:
    """Test uri_to_path function."""

    def test_uri_to_path_file_uri(self, tmp_path):
        """Test uri_to_path converts file:// URI to Path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        uri = f"file://{test_file}"
        path = uri_to_path(uri)

        assert isinstance(path, Path)
        assert path.name == "test.txt"

    def test_uri_to_path_encoded(self):
        """Test uri_to_path handles URL-encoded characters."""
        # Space encoded as %20
        uri = "file:///path/to/file%20with%20spaces.txt"
        path = uri_to_path(uri)

        assert "file with spaces" in str(path)

    def test_uri_to_path_non_uri(self):
        """Test uri_to_path with non-URI string."""
        path_str = "/path/to/file.txt"
        path = uri_to_path(path_str)

        assert isinstance(path, Path)
        assert str(path) == path_str


@pytest.mark.unit
class TestConvertToUri:
    """Test convert_to_uri function."""

    def test_convert_to_uri_vault_uri(self):
        """Test convert_to_uri returns vault:// URI as-is."""
        uri = "vault:///Projects/2025-WKS.md"
        result = convert_to_uri(uri)

        assert result == uri

    def test_convert_to_uri_file_uri(self):
        """Test convert_to_uri returns file:// URI as-is."""
        uri = "file:///Users/test/file.txt"
        result = convert_to_uri(uri)

        assert result == uri

    def test_convert_to_uri_path_string(self, tmp_path):
        """Test convert_to_uri converts path string to file:// URI."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = convert_to_uri(str(test_file))

        assert result.startswith("file://")
        assert "test.txt" in result

    def test_convert_to_uri_path_object(self, tmp_path):
        """Test convert_to_uri converts Path object to file:// URI."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = convert_to_uri(test_file)

        assert result.startswith("file://")
        assert "test.txt" in result

    def test_convert_to_uri_within_vault(self, tmp_path):
        """Test convert_to_uri converts path within vault to vault:// URI."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        test_file = vault_dir / "note.md"
        test_file.write_text("# Note")

        result = convert_to_uri(test_file, vault_path=vault_dir)

        assert result == "vault:///note.md"

    def test_convert_to_uri_outside_vault(self, tmp_path):
        """Test convert_to_uri converts path outside vault to file:// URI."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("content")

        result = convert_to_uri(outside_file, vault_path=vault_dir)

        assert result.startswith("file://")
        assert "outside.txt" in result

    def test_convert_to_uri_vault_path_string(self, tmp_path):
        """Test convert_to_uri with vault_path as string."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        test_file = vault_dir / "note.md"
        test_file.write_text("# Note")

        result = convert_to_uri(test_file, vault_path=str(vault_dir))

        assert result == "vault:///note.md"

    def test_convert_to_uri_vault_path_relative_error(self, tmp_path):
        """Test convert_to_uri handles ValueError when path not relative to vault."""
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("content")

        # Should not raise, just return file:// URI
        result = convert_to_uri(outside_file, vault_path=vault_dir)

        assert result.startswith("file://")

    def test_convert_to_uri_no_vault_path(self, tmp_path):
        """Test convert_to_uri without vault_path uses file://."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = convert_to_uri(test_file, vault_path=None)

        assert result.startswith("file://")
