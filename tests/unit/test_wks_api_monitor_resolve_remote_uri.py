"""Tests for monitor.resolve_remote_uri."""

from pathlib import Path

import pytest

from wks.api.config.URI import URI
from wks.api.monitor.RemoteConfig import RemoteConfig, RemoteMapping
from wks.api.monitor.resolve_remote_uri import resolve_remote_uri


def test_resolve_remote_uri_no_mappings():
    """Test resolution with empty mappings."""
    config = RemoteConfig(mappings=[])
    uri = URI.from_path(Path("/tmp/any"))
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_success():
    """Test successful path resolution."""
    mapping = RemoteMapping(
        local_path="/tmp/wks_test",
        remote_uri="s3://my-bucket/prefix",
    )
    config = RemoteConfig(mappings=[mapping])

    # Path relative to root
    local_path = Path("/tmp/wks_test/subdir/file.txt")
    uri = URI.from_path(local_path)
    result = resolve_remote_uri(uri, config)
    assert result == URI("s3://my-bucket/prefix/subdir/file.txt")


def test_resolve_remote_uri_multiple_mappings():
    """Test resolution with multiple mappings (first match wins)."""
    mappings = [
        RemoteMapping(local_path="/tmp/a", remote_uri="v1://a"),
        RemoteMapping(local_path="/tmp/a/b", remote_uri="v2://b"),
    ]
    config = RemoteConfig(mappings=mappings)

    # Matches /tmp/a first
    path = Path("/tmp/a/b/file.txt")
    uri = URI.from_path(path)
    result = resolve_remote_uri(uri, config)
    assert result == URI("v1://a/b/file.txt")


def test_resolve_remote_uri_no_match():
    """Test resolution with non-matching path."""
    mapping = RemoteMapping(local_path="/tmp/a", remote_uri="v://a")
    config = RemoteConfig(mappings=[mapping])

    path = Path("/tmp/outside")
    uri = URI.from_path(path)
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_invalid_path():
    """Test resolution with invalid path (triggering Exception in normalize_path)."""
    config = RemoteConfig(mappings=[])
    # On many systems, NUL in path triggers error in normalize_path/Path
    # Use URI.from_any which handles invalid paths
    try:
        uri = URI.from_any("/tmp/\x00invalid")
        # If URI creation succeeds, resolve should return None for non-file URIs or invalid paths
        result = resolve_remote_uri(uri, config)
        # Should return None if path resolution failed
        assert result is None
    except (ValueError, OSError):
        # If URI creation fails, that's expected for invalid paths
        pass


def test_resolve_remote_uri_value_error_in_loop(monkeypatch):
    """Test handling of ValueError during mapping iteration."""
    mapping = RemoteMapping(local_path="/tmp/a", remote_uri="v://a")
    config = RemoteConfig(mappings=[mapping])

    # Mock is_relative_to to raise ValueError (simulating some edge case)
    from pathlib import Path

    original_is_relative_to = Path.is_relative_to

    def mock_is_relative_to(self, other):
        if str(other) == "/tmp/a":
            raise ValueError("Test error")
        return original_is_relative_to(self, other)

    monkeypatch.setattr(Path, "is_relative_to", mock_is_relative_to)

    path = Path("/tmp/a/file.txt")
    uri = URI.from_path(path)
    # Should continue loop and return None
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_normalize_failure():
    """Test resolution when invalid type is passed (fail fast)."""
    config = RemoteConfig(mappings=[])
    # Passing an invalid type should raise TypeError (fail fast)
    # We use type: ignore to satisfy Mypy while testing runtime robustness
    with pytest.raises(TypeError, match="uri must be URI"):
        resolve_remote_uri(123, config)  # type: ignore


def test_resolve_remote_uri_with_uri_object():
    """Test resolution with URI object input."""
    mapping = RemoteMapping(
        local_path="/tmp/wks_test",
        remote_uri="s3://my-bucket/prefix",
    )
    config = RemoteConfig(mappings=[mapping])

    # Pass URI object instead of Path
    uri = URI.from_path(Path("/tmp/wks_test/subdir/file.txt"))
    result = resolve_remote_uri(uri, config)
    assert result == URI("s3://my-bucket/prefix/subdir/file.txt")


def test_resolve_remote_uri_with_non_file_uri():
    """Test resolution with non-file URI (should return None)."""
    config = RemoteConfig(mappings=[])
    # Non-file URIs cannot be resolved
    uri = URI("s3://bucket/file.txt")
    assert resolve_remote_uri(uri, config) is None
