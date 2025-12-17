"""Unit tests for glob matching behavior via public monitor API."""

from pathlib import Path

import pytest

from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.matches_glob import matches_glob
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_matches_glob_empty_pattern(tmp_path):
    """Test that empty patterns are skipped (integration test via explain_path)."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {
                    "include_paths": [str(tmp_path)],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": ["", "*.py"],
                    "exclude_globs": [],
                },
                "priority": {
                    "dirs": {},
                    "weights": {
                        "depth_multiplier": 0.9,
                        "underscore_multiplier": 0.5,
                        "only_underscore_multiplier": 0.1,
                        "extension_weights": {},
                    },
                },
                "max_documents": 1000000,
                "min_priority": 0.0,
            }
        }
    )

    test_file = tmp_path / "test.py"
    test_file.write_text("test")

    allowed, _trace = explain_path(cfg, test_file)
    assert allowed is True


def test_matches_glob_exception_handling(monkeypatch):
    """Test exception handling in matches_glob."""

    # Mock fnmatchcase to raise an exception
    def mock_fnmatchcase(*args, **kwargs):
        raise ValueError("Simulated glob error")

    monkeypatch.setattr("fnmatch.fnmatchcase", mock_fnmatchcase)

    path = Path("/tmp/test.txt")
    # Should catch the exception and continue/return False
    assert not matches_glob(["*.txt"], path)


def test_matches_glob_empty_pattern_in_list():
    """Test matches_glob with an empty string in the pattern list."""

    path = Path("/tmp/test.txt")
    # Empty pattern should be skipped
    assert not matches_glob([""], path)
    # Valid pattern should still match if present
    assert matches_glob(["", "*.txt"], path)


def test_matches_glob_matches_by_filename_only():
    """Pattern can match the filename even if it doesn't match the full path."""
    path = Path("dir/test.txt")
    assert matches_glob(["test.txt"], path) is True


def test_matches_glob_matches_by_path_only():
    """Pattern can match the full path even if it doesn't match the filename."""
    path = Path("dir/test.txt")
    assert matches_glob(["dir/*.txt"], path) is True
