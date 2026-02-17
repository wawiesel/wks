"""Unit tests for wks.api.monitor.cmd_filter_add module."""

import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.monitor import cmd_filter_add

pytestmark = pytest.mark.monitor


def test_cmd_filter_add_saves_on_success(monkeypatch):
    """Add filter values successfully.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_unknown_list_name(monkeypatch):
    """Test cmd_filter_add with unknown list_name.

    Requirements:
    - MON-001
    - MON-006
    """
    create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="unknown_list", value="test")
    assert result.success is False
    assert "Unknown list_name" in result.output["errors"][0]


def test_cmd_filter_add_empty_dirname(monkeypatch):
    """Test cmd_filter_add with empty dirname.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_wildcard_in_dirname(monkeypatch):
    """Test cmd_filter_add with wildcard in dirname.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="test*")
    assert result.output["success"] is False
    assert "wildcard characters" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_dirname_in_opposite(monkeypatch):
    """Test cmd_filter_add when dirname already in opposite list.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch, {"filter": {"exclude_dirnames": ["testdir"]}})

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is False
    assert "already present in exclude_dirnames" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_dirname_no_error(monkeypatch):
    """Test cmd_filter_add with valid dirname.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_empty_glob(monkeypatch):
    """Test cmd_filter_add with empty glob.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_globs", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_glob_validation_success(monkeypatch):
    """Test cmd_filter_add with valid glob.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_globs", value="*.py")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_else_branch(monkeypatch):
    """Test cmd_filter_add with non-path, non-dirname, non-glob list.

    Requirements:
    - MON-001
    - MON-006
    """
    # This shouldn't happen with current filter lists, but test the else branch anyway
    pass


def test_cmd_filter_add_validation_error(monkeypatch):
    """Test cmd_filter_add with validation error.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch)

    # Try to add invalid dirname (with path separator)
    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="invalid/path")
    assert result.output["success"] is False
    assert "validation_failed" in result.output
    assert cfg.save_calls == 0


def test_cmd_filter_add_duplicate_dirname(monkeypatch):
    """Test cmd_filter_add with duplicate dirname.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch, {"filter": {"include_dirnames": ["testdir"]}})

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is False
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 0


def test_cmd_filter_add_duplicate_glob(monkeypatch):
    """Test cmd_filter_add with duplicate glob.

    Requirements:
    - MON-001
    - MON-006
    """
    cfg = create_tracked_wks_config(monkeypatch, {"filter": {"include_globs": ["*.md"]}})

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_globs", value="*.md")
    assert result.output["success"] is False
    assert result.output["already_exists"] is True
    assert cfg.save_calls == 0


def test_cmd_filter_add_internal_error(monkeypatch):
    """Test cmd_filter_add throws RuntimeError if validate_value returns (None, None).

    Requirements:
    - MON-001
    - MON-006
    """
    create_tracked_wks_config(monkeypatch)

    import wks.api.monitor.cmd_filter_add as filter_add_mod

    monkeypatch.setattr(filter_add_mod, "validate_value", lambda *args: (None, None))

    with pytest.raises(RuntimeError, match="value_to_store should not be None"):
        run_cmd(filter_add_mod.cmd_filter_add, list_name="include_paths", value="test")
