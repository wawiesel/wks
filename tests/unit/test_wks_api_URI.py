import socket
from pathlib import Path

import pytest

from wks.api.config.URI import URI


def test_uri_creation_valid():
    uri = URI("file://host/path/to/file")
    assert uri.value == "file://host/path/to/file"
    assert str(uri) == "file://host/path/to/file"
    assert repr(uri) == "URI('file://host/path/to/file')"


@pytest.mark.parametrize(
    ("value", "exc_type", "match"),
    [
        ("not-a-uri", ValueError, "Invalid URI format"),
        (123, TypeError, "URI value must be a string"),
    ],
)
def test_uri_creation_invalid(value, exc_type, match):
    with pytest.raises(exc_type, match=match):
        URI(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("source", [Path("/tmp/test/file.txt"), "/tmp/test/file.txt"])
def test_uri_from_path(source):
    expected_path = Path(source).expanduser().absolute()
    uri = URI.from_path(source)
    hostname = socket.gethostname()

    assert uri.value == f"file://{hostname}{expected_path}"
    assert uri.is_file is True
    assert uri.is_vault is False


def test_uri_from_any_returns_uri_instance():
    original_uri = URI("vault:///note.md")
    assert URI.from_any(original_uri) is original_uri
    assert URI.from_any("file://host/path").value == "file://host/path"
    assert URI.from_any("vault:///note.md").value == "vault:///note.md"


@pytest.mark.parametrize(
    ("use_string_path", "inside_vault", "expect_vault"),
    [
        (False, True, True),
        (True, True, True),
        (False, False, False),
        (True, False, False),
    ],
)
def test_uri_from_any_path_variants(tmp_path, use_string_path, inside_vault, expect_vault):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    file_path = (vault_path / "note.md") if inside_vault else (tmp_path / "outside" / "file.txt")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("test")
    source = str(file_path) if use_string_path else file_path

    uri = URI.from_any(source, vault_path=vault_path)

    assert uri.is_vault is expect_vault
    assert uri.is_file is (not expect_vault)
    if expect_vault:
        assert uri.value == "vault:///note.md"
    else:
        assert uri.value.startswith(f"file://{socket.gethostname()}")


def test_uri_from_any_path_without_vault(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    uri = URI.from_any(file_path)
    assert uri.is_file is True
    assert uri.value.startswith(f"file://{socket.gethostname()}")


@pytest.mark.parametrize(
    ("value", "is_file", "is_vault"),
    [
        ("file://host/path", True, False),
        ("vault:///path", False, True),
        ("http://example.com", False, False),
    ],
)
def test_uri_scheme_flags(value, is_file, is_vault):
    uri = URI(value)
    assert uri.is_file is is_file
    assert uri.is_vault is is_vault


def test_uri_to_path_file_uri():
    test_path = Path("/tmp/test/file.txt")
    assert URI.from_path(test_path).to_path() == test_path.expanduser().absolute()


def test_uri_to_path_vault_uri():
    vault_path = Path("/tmp/vault")
    assert URI("vault:///note.md").to_path(vault_path=vault_path) == vault_path / "note.md"


@pytest.mark.parametrize(
    ("uri", "match"),
    [
        (URI("vault:///note.md"), "Cannot resolve vault URI without vault_path"),
        (URI("http://example.com/file"), "Cannot resolve local path from URI"),
    ],
)
def test_uri_to_path_errors(uri, match):
    with pytest.raises(ValueError, match=match):
        uri.to_path()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("file://myhost/Users/test/file.txt", Path("/Users/test/file.txt")),
        ("file://host/Users/test%20file.txt", Path("/Users/test file.txt")),
        ("file://hostname", Path("/")),
    ],
)
def test_uri_path_property_success(value, expected):
    assert URI(value).path == expected


def test_uri_path_property_file_uri_from_hostname():
    test_path = Path("/tmp/test/file.txt")
    hostname = socket.gethostname()
    assert URI(f"file://{hostname}{test_path}").path == test_path.expanduser().absolute()


def test_uri_path_property_non_file_uri():
    with pytest.raises(ValueError, match="Cannot extract local path from non-file URI"):
        _ = URI("vault:///note.md").path


def test_uri_to_path_relative_file_uri_round_trip():
    test_path = Path("/tmp/test/file.txt")
    hostname = socket.gethostname()
    assert URI(f"file://{hostname}{test_path}").to_path() == test_path.expanduser().absolute()
