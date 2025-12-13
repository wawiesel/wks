"""Unit tests for calculate_priority function."""

from pathlib import Path

import pytest

from wks.api.monitor.calculate_priority import calculate_priority

pytestmark = pytest.mark.monitor


def test_calculate_priority_no_priority_dir(tmp_path):
    """Test that files outside priority directories return 0.0."""
    priority_dirs = {str(tmp_path / "other"): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    assert priority == 0.0


def test_calculate_priority_base_priority(tmp_path):
    """Test that files in priority directory use base priority."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    assert priority == 100.0


def test_calculate_priority_depth_multiplier(tmp_path):
    """Test that depth multiplier is applied for nested directories."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "subdir" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) for subdir
    assert priority == pytest.approx(90.0)


def test_calculate_priority_multiple_depth_levels(tmp_path):
    """Test that depth multiplier is applied for each directory level."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "level1" / "level2" / "file.txt"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * 0.9 * 0.9 for two levels
    assert priority == pytest.approx(81.0)


def test_calculate_priority_underscore_multiplier(tmp_path):
    """Test that underscore multiplier is applied for leading underscores."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "_private" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) * underscore_multiplier (0.5) for one underscore
    assert priority == pytest.approx(45.0)


def test_calculate_priority_multiple_underscores(tmp_path):
    """Test that underscore multiplier is applied per underscore."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "__private" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) * 0.5^2 for two underscores
    assert priority == pytest.approx(22.5)


def test_calculate_priority_only_underscore(tmp_path):
    """Test that only_underscore_multiplier is used for component that is exactly '_'."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "_" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) * only_underscore_multiplier (0.1)
    assert priority == pytest.approx(9.0)


def test_calculate_priority_extension_weight(tmp_path):
    """Test that extension weights are applied."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {".py": 2.0, ".txt": 0.5},
    }

    test_file = tmp_path / "file.py"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * extension_weight (2.0)
    assert priority == pytest.approx(200.0)


def test_calculate_priority_extension_default_weight(tmp_path):
    """Test that unspecified extensions use default weight of 1.0."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {".py": 2.0},
    }

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * default extension weight (1.0)
    assert priority == pytest.approx(100.0)


def test_calculate_priority_filename_underscore(tmp_path):
    """Test that filename stems starting with underscore get penalty."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "_file.txt"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) for filename * underscore_multiplier (0.5)
    assert priority == pytest.approx(45.0)


def test_calculate_priority_filename_exactly_underscore(tmp_path):
    """Test that filename stem that is exactly '_' uses only_underscore_multiplier."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "_.txt"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * depth_multiplier (0.9) * only_underscore_multiplier (0.1)
    assert priority == pytest.approx(9.0)


def test_calculate_priority_deepest_match(tmp_path):
    """Test that deepest matching priority directory is used."""
    priority_dirs = {
        str(tmp_path): 100.0,
        str(tmp_path / "subdir"): 200.0,
    }
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "subdir" / "file.txt"
    test_file.parent.mkdir()
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Should use deeper match (200.0) as base
    assert priority == pytest.approx(200.0)


def test_calculate_priority_complex_case(tmp_path):
    """Test a complex case with all multipliers."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {".py": 2.0},
    }

    test_file = tmp_path / "level1" / "_private" / "__file.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * 0.9 (level1) * 0.9 (depth for _private) * 0.5 (underscore)
    # * 0.9 (depth for filename) * 0.5^2 (two underscores) * 2.0 (extension)
    expected = 100.0 * 0.9 * 0.9 * 0.5 * 0.9 * 0.5 * 0.5 * 2.0
    assert priority == pytest.approx(expected)


def test_calculate_priority_no_extension(tmp_path):
    """Test that files without extensions work correctly."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "file"
    test_file.write_text("test")

    priority = calculate_priority(test_file, priority_dirs, weights)
    # Base (100.0) * default extension weight (1.0)
    assert priority == pytest.approx(100.0)


def test_calculate_priority_valueerror_different_drives(monkeypatch, tmp_path):
    """Test calculate_priority when paths are on different drives (Windows case)."""
    priority_dirs = {str(tmp_path): 100.0}
    weights = {
        "depth_multiplier": 0.9,
        "underscore_multiplier": 0.5,
        "only_underscore_multiplier": 0.1,
        "extension_weights": {},
    }

    test_file = tmp_path / "file.txt"
    test_file.write_text("test")

    # Mock relative_to to raise ValueError (simulating different drives)
    original_relative_to = Path.relative_to

    def mock_relative_to(self, other):
        if other == tmp_path.resolve():
            raise ValueError("Paths are on different drives")
        return original_relative_to(self, other)

    monkeypatch.setattr("pathlib.Path.relative_to", mock_relative_to)

    # Should fall back to path.parts
    priority = calculate_priority(test_file, priority_dirs, weights)
    # Should still calculate priority using full path parts
    assert priority > 0.0
