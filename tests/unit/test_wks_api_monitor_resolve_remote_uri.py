from pathlib import Path

import pytest

from wks.api.config.URI import URI
from wks.api.monitor.RemoteConfig import RemoteConfig, RemoteMapping
from wks.api.monitor.resolve_remote_uri import resolve_remote_uri


def test_resolve_remote_uri_no_mappings():
    config = RemoteConfig(mappings=[])
    uri = URI.from_path(Path("/tmp/any"))
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_success():
    mapping = RemoteMapping(
        local_path="/tmp/wks_test",
        remote_uri="s3://my-bucket/prefix",
    )
    config = RemoteConfig(mappings=[mapping])

    local_path = Path("/tmp/wks_test/subdir/file.txt")
    uri = URI.from_path(local_path)
    result = resolve_remote_uri(uri, config)
    assert result == URI("s3://my-bucket/prefix/subdir/file.txt")


def test_resolve_remote_uri_multiple_mappings():
    mappings = [
        RemoteMapping(local_path="/tmp/a", remote_uri="v1://a"),
        RemoteMapping(local_path="/tmp/a/b", remote_uri="v2://b"),
    ]
    config = RemoteConfig(mappings=mappings)

    path = Path("/tmp/a/b/file.txt")
    uri = URI.from_path(path)
    result = resolve_remote_uri(uri, config)
    assert result == URI("v1://a/b/file.txt")


def test_resolve_remote_uri_no_match():
    mapping = RemoteMapping(local_path="/tmp/a", remote_uri="v://a")
    config = RemoteConfig(mappings=[mapping])

    path = Path("/tmp/outside")
    uri = URI.from_path(path)
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_invalid_path():
    config = RemoteConfig(mappings=[])
    try:
        uri = URI.from_any("/tmp/\x00invalid")
        result = resolve_remote_uri(uri, config)
        assert result is None
    except (ValueError, OSError):
        pass


def test_resolve_remote_uri_value_error_in_loop(monkeypatch):
    mapping = RemoteMapping(local_path="/tmp/a", remote_uri="v://a")
    config = RemoteConfig(mappings=[mapping])

    from pathlib import Path

    original_is_relative_to = Path.is_relative_to

    def mock_is_relative_to(self, other):
        if str(other) == "/tmp/a":
            raise ValueError("Test error")
        return original_is_relative_to(self, other)

    monkeypatch.setattr(Path, "is_relative_to", mock_is_relative_to)

    path = Path("/tmp/a/file.txt")
    uri = URI.from_path(path)
    assert resolve_remote_uri(uri, config) is None


def test_resolve_remote_uri_normalize_failure():
    config = RemoteConfig(mappings=[])
    with pytest.raises(TypeError, match="uri must be URI"):
        resolve_remote_uri(123, config)  # type: ignore


def test_resolve_remote_uri_with_uri_object():
    mapping = RemoteMapping(
        local_path="/tmp/wks_test",
        remote_uri="s3://my-bucket/prefix",
    )
    config = RemoteConfig(mappings=[mapping])

    uri = URI.from_path(Path("/tmp/wks_test/subdir/file.txt"))
    result = resolve_remote_uri(uri, config)
    assert result == URI("s3://my-bucket/prefix/subdir/file.txt")


def test_resolve_remote_uri_with_non_file_uri():
    config = RemoteConfig(mappings=[])
    uri = URI("s3://bucket/file.txt")
    assert resolve_remote_uri(uri, config) is None
