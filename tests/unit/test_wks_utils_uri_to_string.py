"""Tests for uri_to_string helper."""

from wks.api.config.uri_to_string import uri_to_string
from wks.api.URI import URI


def test_uri_to_string_with_uri_object():
    """Test uri_to_string with URI object."""
    uri = URI("file://host/path/to/file")
    result = uri_to_string(uri)
    assert result == "file://host/path/to/file"
    assert isinstance(result, str)


def test_uri_to_string_with_string():
    """Test uri_to_string with string (returns as-is)."""
    uri_str = "file://host/path/to/file"
    result = uri_to_string(uri_str)
    assert result == uri_str
    assert result is uri_str  # Should return same object


def test_uri_to_string_with_vault_uri():
    """Test uri_to_string with vault URI."""
    uri = URI("vault:///note.md")
    result = uri_to_string(uri)
    assert result == "vault:///note.md"
