"""Tests for URI value object."""

from pathlib import Path

import pytest

from wks.api.config.URI import URI


def test_uri_creation_valid():
    """Test creating URI with valid format."""
    uri = URI("file://host/path/to/file")
    assert uri.value == "file://host/path/to/file"
    assert str(uri) == "file://host/path/to/file"
    assert repr(uri) == "URI('file://host/path/to/file')"


def test_uri_creation_invalid_missing_scheme():
    """Test URI creation fails with invalid format (no scheme)."""
    with pytest.raises(ValueError, match="Invalid URI format"):
        URI("not-a-uri")


def test_uri_creation_invalid_not_string():
    """Test URI creation fails with non-string value."""
    with pytest.raises(TypeError, match="URI value must be a string"):
        URI(123)  # type: ignore


def test_uri_from_path():
    """Test creating URI from file path."""
    import socket

    test_path = Path("/tmp/test/file.txt")
    uri = URI.from_path(test_path)

    hostname = socket.gethostname()
    assert uri.value == f"file://{hostname}{test_path}"
    assert uri.is_file is True
    assert uri.is_vault is False


def test_uri_from_path_string():
    """Test creating URI from string path."""
    import socket

    test_path = "/tmp/test/file.txt"
    uri = URI.from_path(test_path)

    hostname = socket.gethostname()
    assert uri.value == f"file://{hostname}{Path(test_path).expanduser().absolute()}"


def test_uri_from_any_uri_object():
    """Test from_any returns URI object as-is."""
    original_uri = URI("vault:///note.md")
    result = URI.from_any(original_uri)
    assert result is original_uri  # Should return same object


def test_uri_from_any_uri_string():
    """Test from_any with URI string."""
    uri = URI.from_any("file://host/path")
    assert isinstance(uri, URI)
    assert uri.value == "file://host/path"


def test_uri_from_any_path_with_vault():
    """Test from_any converts path to vault URI when in vault."""
    vault_path = Path("/tmp/vault")
    file_path = vault_path / "note.md"

    # Create vault directory and file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("test")

    try:
        uri = URI.from_any(file_path, vault_path=vault_path)
        assert uri.is_vault is True
        assert uri.value == "vault:///note.md"
    finally:
        file_path.unlink()
        file_path.parent.rmdir()


def test_uri_from_any_path_outside_vault():
    """Test from_any converts path to file URI when outside vault."""
    vault_path = Path("/tmp/vault")
    file_path = Path("/tmp/outside/file.txt")

    # Create file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("test")

    try:
        import socket

        uri = URI.from_any(file_path, vault_path=vault_path)
        assert uri.is_file is True
        hostname = socket.gethostname()
        assert uri.value.startswith(f"file://{hostname}")
    finally:
        file_path.unlink()
        file_path.parent.rmdir()


def test_uri_from_any_path_no_vault():
    """Test from_any converts path to file URI when no vault specified."""
    file_path = Path("/tmp/test/file.txt")

    # Create file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("test")

    try:
        import socket

        uri = URI.from_any(file_path)
        assert uri.is_file is True
        hostname = socket.gethostname()
        assert uri.value.startswith(f"file://{hostname}")
    finally:
        file_path.unlink()
        file_path.parent.rmdir()


def test_uri_is_file():
    """Test is_file property."""
    assert URI("file://host/path").is_file is True
    assert URI("vault:///path").is_file is False
    assert URI("http://example.com").is_file is False


def test_uri_is_vault():
    """Test is_vault property."""
    assert URI("vault:///path").is_vault is True
    assert URI("file://host/path").is_vault is False
    assert URI("http://example.com").is_vault is False


def test_uri_to_path_file_uri():
    """Test to_path with file URI."""
    test_path = Path("/tmp/test/file.txt")
    uri = URI.from_path(test_path)

    resolved = uri.to_path()
    assert resolved == test_path.expanduser().absolute()


def test_uri_to_path_vault_uri_with_vault_path():
    """Test to_path with vault URI and vault_path."""
    vault_path = Path("/tmp/vault")
    uri = URI("vault:///note.md")

    resolved = uri.to_path(vault_path=vault_path)
    assert resolved == vault_path / "note.md"


def test_uri_to_path_vault_uri_without_vault_path():
    """Test to_path with vault URI fails without vault_path."""
    uri = URI("vault:///note.md")

    with pytest.raises(ValueError, match="Cannot resolve vault URI without vault_path"):
        uri.to_path()


def test_uri_to_path_unsupported_scheme():
    """Test to_path with unsupported URI scheme."""
    uri = URI("http://example.com/file")

    with pytest.raises(ValueError, match="Cannot resolve local path from URI"):
        uri.to_path()


def test_uri_path_property_file_uri():
    """Test path property with file URI."""
    import socket

    test_path = Path("/tmp/test/file.txt")
    hostname = socket.gethostname()
    uri = URI(f"file://{hostname}{test_path}")

    resolved = uri.path
    assert resolved == test_path.expanduser().absolute()


def test_uri_path_property_non_file_uri():
    """Test path property fails with non-file URI."""
    uri = URI("vault:///note.md")

    with pytest.raises(ValueError, match="Cannot extract local path from non-file URI"):
        _ = uri.path


def test_uri_path_property_with_hostname():
    """Test path property handles file URI with hostname."""
    uri = URI("file://myhost/Users/test/file.txt")
    path = uri.path
    assert path == Path("/Users/test/file.txt")


def test_uri_path_property_url_encoded():
    """Test path property handles URL-encoded paths."""
    uri = URI("file://host/Users/test%20file.txt")
    path = uri.path
    assert path == Path("/Users/test file.txt")


def test_uri_path_property_no_slash_after_hostname():
    """Test path property handles file URI with no slash after hostname."""
    uri = URI("file://hostname")
    path = uri.path
    assert path == Path("/")


def test_uri_to_path_file_uri_with_relative_path():
    """Test to_path with file URI that has relative path component."""
    import socket

    hostname = socket.gethostname()
    test_path = Path("/tmp/test/file.txt")
    uri = URI(f"file://{hostname}{test_path}")
    resolved = uri.to_path()
    assert resolved == test_path.expanduser().absolute()


def test_uri_from_any_path_string_with_vault():
    """Test from_any with string path and vault_path."""
    vault_path = Path("/tmp/vault")
    file_path_str = str(vault_path / "note.md")

    # Create vault directory and file
    Path(file_path_str).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path_str).write_text("test")

    try:
        uri = URI.from_any(file_path_str, vault_path=vault_path)
        assert uri.is_vault is True
        assert uri.value == "vault:///note.md"
    finally:
        Path(file_path_str).unlink()
        Path(file_path_str).parent.rmdir()


def test_uri_from_any_uri_string_vault():
    """Test from_any with vault URI string."""
    uri = URI.from_any("vault:///note.md")
    assert uri.is_vault is True
    assert uri.value == "vault:///note.md"


def test_uri_from_any_uri_string_file():
    """Test from_any with file URI string."""
    import socket

    hostname = socket.gethostname()
    uri = URI.from_any(f"file://{hostname}/tmp/test")
    assert uri.is_file is True
    assert uri.value == f"file://{hostname}/tmp/test"
