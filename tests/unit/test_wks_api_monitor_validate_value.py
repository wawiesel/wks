"""Unit tests for _validate_value module."""

import pytest

from wks.api.monitor import validate_value

pytestmark = pytest.mark.monitor


class _DummyFilter:
    def __init__(self):
        self.include_dirnames = ["foo"]
        self.exclude_dirnames = ["bar"]


class _DummyConfig:
    def __init__(self):
        self.filter = _DummyFilter()


def test_validate_value_path_resolution(tmp_path, monkeypatch):
    """Test path resolution logic."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home_path = tmp_path / "docs"
    home_path.mkdir()

    # Path inside home should become tilde-prefixed
    val, err = validate_value("include_paths", str(home_path), None)
    assert val == "~/docs"
    assert err is None

    # Path outside home stays absolute
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    val, err = validate_value("include_paths", str(outside), None)
    assert val == str(outside.resolve())
    assert err is None


def test_validate_value_dirnames():
    """Test dirname validation logic."""
    cfg = _DummyConfig()

    # Empty
    val, err = validate_value("include_dirnames", "  ", cfg)
    assert err == "Directory name cannot be empty"

    # Wildcards
    val, err = validate_value("include_dirnames", "foo*", cfg)
    assert err == "Directory names cannot contain wildcard characters"

    # Path separators
    val, err = validate_value("include_dirnames", "foo/bar", cfg)
    assert err == "Directory names cannot contain path separators"
    val, err = validate_value("include_dirnames", "foo\\bar", cfg)
    assert err == "Directory names cannot contain path separators"

    # Duplicate in opposite list (adding to include, present in exclude)
    val, err = validate_value("include_dirnames", "bar", cfg)
    assert "already present in exclude_dirnames" in err

    # Valid
    val, err = validate_value("include_dirnames", "baz", cfg)
    assert val == "baz"
    assert err is None


def test_validate_value_globs(monkeypatch):
    """Test glob validation logic."""
    # Empty
    val, err = validate_value("include_globs", "  ", None)
    assert err == "Glob pattern cannot be empty"

    # Valid
    val, err = validate_value("include_globs", "*.py", None)
    assert val == "*.py"
    assert err is None

    # Invalid glob syntax (mocking exception)
    def mock_fnmatch(name, pat):
        raise Exception("Boom")

    monkeypatch.setattr("fnmatch.fnmatch", mock_fnmatch)
    val, err = validate_value("include_globs", "[", None)
    assert "Invalid glob syntax" in err


def test_validate_value_passthrough_for_unknown_list():
    """Values for unknown lists are passed through unchanged."""
    cfg = _DummyConfig()
    val, err = validate_value("custom_list", "  data  ", cfg)
    assert val == "data"
    assert err is None
