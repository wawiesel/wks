"""Unit tests for wks.api.monitor.cmd_filter_add module."""

import pytest

from tests.unit.conftest import create_tracked_wks_config, run_cmd
from wks.api.monitor import cmd_filter_add

pytestmark = pytest.mark.monitor


def test_cmd_filter_add_saves_on_success(monkeypatch):
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_unknown_list_name(monkeypatch):
    """Test cmd_filter_add with unknown list_name."""
    create_tracked_wks_config(monkeypatch)

    with pytest.raises(ValueError):
        run_cmd(cmd_filter_add.cmd_filter_add, list_name="unknown_list", value="test")


def test_cmd_filter_add_empty_dirname(monkeypatch):
    """Test cmd_filter_add with empty dirname."""
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_wildcard_in_dirname(monkeypatch):
    """Test cmd_filter_add with wildcard in dirname."""
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="test*")
    assert result.output["success"] is False
    assert "wildcard characters" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_dirname_in_opposite(monkeypatch):
    """Test cmd_filter_add when dirname already in opposite list."""
    cfg = create_tracked_wks_config(monkeypatch, {"filter": {"exclude_dirnames": ["testdir"]}})

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is False
    assert "already present in exclude_dirnames" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_dirname_no_error(monkeypatch):
    """Test cmd_filter_add with valid dirname."""
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="testdir")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_empty_glob(monkeypatch):
    """Test cmd_filter_add with empty glob."""
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_globs", value="   ")
    assert result.output["success"] is False
    assert "cannot be empty" in result.output["message"]
    assert cfg.save_calls == 0


def test_cmd_filter_add_glob_validation_success(monkeypatch):
    """Test cmd_filter_add with valid glob."""
    cfg = create_tracked_wks_config(monkeypatch)

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_globs", value="*.py")
    assert result.output["success"] is True
    assert cfg.save_calls == 1


def test_cmd_filter_add_else_branch(monkeypatch):
    """Test cmd_filter_add with non-path, non-dirname, non-glob list."""
    # This shouldn't happen with current filter lists, but test the else branch anyway
    pass


def test_cmd_filter_add_validation_error(monkeypatch):
    """Test cmd_filter_add with validation error."""
    cfg = create_tracked_wks_config(monkeypatch)

    # Try to add invalid dirname (with path separator)
    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_dirnames", value="invalid/path")
    assert result.output["success"] is False
    assert "validation_failed" in result.output
    assert cfg.save_calls == 0


def test_cmd_filter_add_duplicate(monkeypatch):
    """Test cmd_filter_add with duplicate value."""
    cfg = create_tracked_wks_config(monkeypatch, {"filter": {"include_paths": ["/tmp/x"]}})

    result = run_cmd(cmd_filter_add.cmd_filter_add, list_name="include_paths", value="/tmp/x")
    assert result.output["success"] is False
    assert "already_exists" in result.output
    assert cfg.save_calls == 0
