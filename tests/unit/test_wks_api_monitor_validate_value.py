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
    monkeypatch.setenv("HOME", str(tmp_path))
    home_path = tmp_path / "docs"
    home_path.mkdir()

    val, err = validate_value("include_paths", str(home_path), None)
    assert val == "~/docs"
    assert err is None

    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    val, err = validate_value("include_paths", str(outside), None)
    assert val == str(outside.resolve())
    assert err is None

    val, err = validate_value("exclude_paths", str(home_path), None)
    assert val == "~/docs"
    assert err is None

    val, err = validate_value("exclude_paths", str(outside), None)
    assert val == str(outside.resolve())
    assert err is None


def test_validate_value_dirnames():
    cfg = _DummyConfig()

    val, err = validate_value("include_dirnames", "  ", cfg)
    assert err == "Directory name cannot be empty"

    val, err = validate_value("include_dirnames", "foo*", cfg)
    assert err == "Directory names cannot contain wildcard characters"

    val, err = validate_value("include_dirnames", "foo/bar", cfg)
    assert err == "Directory names cannot contain path separators"
    val, err = validate_value("include_dirnames", "foo\\bar", cfg)
    assert err == "Directory names cannot contain path separators"

    val, err = validate_value("include_dirnames", "bar", cfg)
    assert err is not None
    assert "already present in exclude_dirnames" in err

    val, err = validate_value("include_dirnames", "baz", cfg)
    assert val == "baz"
    assert err is None

    val, err = validate_value("exclude_dirnames", "  ", cfg)
    assert err == "Directory name cannot be empty"

    val, err = validate_value("exclude_dirnames", "foo*", cfg)
    assert err == "Directory names cannot contain wildcard characters"


def test_validate_value_globs(monkeypatch):
    val, err = validate_value("include_globs", "  ", None)
    assert err == "Glob pattern cannot be empty"

    val, err = validate_value("include_globs", "*.py", None)
    assert val == "*.py"
    assert err is None

    def mock_fnmatch(name, pat):
        raise Exception("Boom")

    monkeypatch.setattr("fnmatch.fnmatch", mock_fnmatch)
    val, err = validate_value("include_globs", "[", None)
    assert err is not None
    assert "Invalid glob syntax" in err


def test_validate_value_passthrough_for_unknown_list():
    cfg = _DummyConfig()
    val, err = validate_value("custom_list", "  data  ", cfg)
    assert val == "data"
    assert err is None


def test_validate_value_path_home_edge_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home_path = tmp_path / "docs"
    home_path.mkdir()

    val, err = validate_value("include_paths", str(tmp_path), None)
    assert err is None
    assert val is not None
    assert val == "~" or val.startswith("~")

    val, err = validate_value("include_paths", f"{home_path}/", None)
    assert val == "~/docs"
    assert err is None


def test_validate_value_dirname_edge_cases():
    cfg = _DummyConfig()

    _val, err = validate_value("include_dirnames", "\t\n\r", cfg)
    assert err == "Directory name cannot be empty"

    _val, err = validate_value("include_dirnames", "test[0-9]*", cfg)
    assert err == "Directory names cannot contain wildcard characters"

    _val, err = validate_value("include_dirnames", "test\\dir", cfg)
    assert err == "Directory names cannot contain path separators"


def test_validate_value_glob_edge_cases():
    val, err = validate_value("include_globs", "**/*.py", None)
    assert val == "**/*.py"
    assert err is None

    val, err = validate_value("include_globs", "[a-z]*.txt", None)
    assert val == "[a-z]*.txt"
    assert err is None
