"""Unit tests for _validate_value module."""

import pytest

from wks.api.monitor.validate_value import validate_value

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

    # exclude_paths should behave the same as include_paths for normalization
    val, err = validate_value("exclude_paths", str(home_path), None)
    assert val == "~/docs"
    assert err is None

    val, err = validate_value("exclude_paths", str(outside), None)
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
    assert err is not None
    assert "already present in exclude_dirnames" in err

    # Valid
    val, err = validate_value("include_dirnames", "baz", cfg)
    assert val == "baz"
    assert err is None

    # exclude_dirnames should validate the same shape as include_dirnames
    val, err = validate_value("exclude_dirnames", "  ", cfg)
    assert err == "Directory name cannot be empty"

    val, err = validate_value("exclude_dirnames", "foo*", cfg)
    assert err == "Directory names cannot contain wildcard characters"


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
    assert err is not None
    assert "Invalid glob syntax" in err


def test_validate_value_passthrough_for_unknown_list():
    """Values for unknown lists are passed through unchanged."""
    cfg = _DummyConfig()
    val, err = validate_value("custom_list", "  data  ", cfg)
    assert val == "data"
    assert err is None


def test_validate_value_path_home_edge_cases(tmp_path, monkeypatch):
    """Test validate_value path handling for edge cases."""
    monkeypatch.setenv("HOME", str(tmp_path))
    home_path = tmp_path / "docs"
    home_path.mkdir()

    # Test path exactly at home - should become "~" or "~/" depending on canonicalize_path
    val, err = validate_value("include_paths", str(tmp_path), None)
    # canonicalize_path will resolve it, and if it matches HOME, it becomes ~
    # The exact behavior depends on canonicalize_path implementation
    assert err is None
    # It should either be "~" or start with "~"
    assert val is not None
    assert val == "~" or val.startswith("~")

    # Test path with trailing slash
    val, err = validate_value("include_paths", f"{home_path}/", None)
    assert val == "~/docs"
    assert err is None


def test_validate_value_dirname_edge_cases():
    """Test validate_value dirname validation edge cases."""
    cfg = _DummyConfig()

    # Test with only whitespace after strip
    _val, err = validate_value("include_dirnames", "\t\n\r", cfg)
    assert err == "Directory name cannot be empty"

    # Test with mixed wildcards
    _val, err = validate_value("include_dirnames", "test[0-9]*", cfg)
    assert err == "Directory names cannot contain wildcard characters"

    # Test with backslash (Windows path separator)
    _val, err = validate_value("include_dirnames", "test\\dir", cfg)
    assert err == "Directory names cannot contain path separators"


def test_validate_value_glob_edge_cases():
    """Test validate_value glob validation edge cases."""
    # Test with complex glob pattern
    val, err = validate_value("include_globs", "**/*.py", None)
    assert val == "**/*.py"
    assert err is None

    # Test with glob pattern that has special chars
    val, err = validate_value("include_globs", "[a-z]*.txt", None)
    assert val == "[a-z]*.txt"
    assert err is None
