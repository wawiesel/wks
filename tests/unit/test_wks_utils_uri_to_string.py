from wks.api.config.URI import URI
from wks.api.config.uri_to_string import uri_to_string


def test_uri_to_string_with_uri_object():
    uri = URI("file://host/path/to/file")
    result = uri_to_string(uri)
    assert result == "file://host/path/to/file"
    assert isinstance(result, str)


def test_uri_to_string_with_string():
    uri_str = "file://host/path/to/file"
    result = uri_to_string(uri_str)
    assert result == uri_str
    assert result is uri_str  # Should return same object


def test_uri_to_string_with_vault_uri():
    uri = URI("vault:///note.md")
    result = uri_to_string(uri)
    assert result == "vault:///note.md"
