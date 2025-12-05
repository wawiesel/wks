"""Unit tests for find_priority_dir function."""

from pathlib import Path

import pytest

from wks.api.monitor.find_priority_dir import find_priority_dir
pytestmark = pytest.mark.monitor


def test_find_priority_dir_no_match(tmp_path):
    """Test that paths outside all priority directories return None."""
    priority_dirs = {str(tmp_path / "other"): 100.0}

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir is None
    assert base_priority == 100.0  # Default when no match


def test_find_priority_dir_exact_match(tmp_path):
    """Test that exact match returns the priority directory."""
    priority_dirs = {str(tmp_path): 100.0}

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == tmp_path.resolve()
    assert base_priority == 100.0


def test_find_priority_dir_nested_file(tmp_path):
    """Test that nested files match their parent priority directory."""
    priority_dirs = {str(tmp_path): 100.0}

    test_file = tmp_path / "subdir" / "nested" / "file.txt"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == tmp_path.resolve()
    assert base_priority == 100.0


def test_find_priority_dir_deepest_match(tmp_path):
    """Test that deepest matching priority directory is returned."""
    priority_dirs = {
        str(tmp_path): 100.0,
        str(tmp_path / "subdir"): 200.0,
    }

    test_file = tmp_path / "subdir" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == (tmp_path / "subdir").resolve()
    assert base_priority == 200.0


def test_find_priority_dir_deepest_match_nested(tmp_path):
    """Test that deepest match works with multiple nested priority directories."""
    priority_dirs = {
        str(tmp_path): 100.0,
        str(tmp_path / "level1"): 200.0,
        str(tmp_path / "level1" / "level2"): 300.0,
    }

    test_file = tmp_path / "level1" / "level2" / "level3" / "file.txt"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == (tmp_path / "level1" / "level2").resolve()
    assert base_priority == 300.0


def test_find_priority_dir_tilde_expansion(tmp_path, monkeypatch):
    """Test that tilde paths are expanded correctly."""
    home = Path.home()
    priority_dirs = {"~/test": 100.0}

    test_file = home / "test" / "file.txt"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == (home / "test").resolve()
    assert base_priority == 100.0


def test_find_priority_dir_relative_paths(tmp_path):
    """Test that relative paths in priority_dirs are resolved."""
    priority_dirs = {".": 100.0}

    # Change to tmp_path directory
    original_cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")

        priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

        assert priority_dir == tmp_path.resolve()
        assert base_priority == 100.0
    finally:
        os.chdir(original_cwd)


def test_find_priority_dir_multiple_matches_shallow(tmp_path):
    """Test that when multiple matches exist, the deepest is chosen."""
    priority_dirs = {
        str(tmp_path): 100.0,
        str(tmp_path / "a"): 200.0,
        str(tmp_path / "b"): 300.0,
    }

    # File in 'a' should match 'a', not root or 'b'
    test_file = tmp_path / "a" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir == (tmp_path / "a").resolve()
    assert base_priority == 200.0


def test_find_priority_dir_empty_dict(tmp_path):
    """Test that empty priority_dirs returns None."""
    priority_dirs = {}

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority_dir, base_priority = find_priority_dir(test_file, priority_dirs)

    assert priority_dir is None
    assert base_priority == 100.0  # Default


def test_find_priority_dir_path_resolution(tmp_path):
    """Test that paths are resolved before matching."""
    # Create a symlink scenario or use resolved paths
    priority_dirs = {str(tmp_path.resolve()): 100.0}

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    # Use a path that might not be resolved
    test_path = Path(str(test_file))

    priority_dir, base_priority = find_priority_dir(test_path, priority_dirs)

    assert priority_dir == tmp_path.resolve()
    assert base_priority == 100.0

