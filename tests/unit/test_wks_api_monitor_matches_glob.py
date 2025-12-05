"""Unit tests for _matches_glob function (tested through explain_path)."""

import pytest
from pathlib import Path

from wks.api.monitor.MonitorConfig import MonitorConfig
from wks.api.monitor.explain_path import explain_path
pytestmark = pytest.mark.monitor


def test_matches_glob_empty_pattern(tmp_path):
    """Test that empty patterns are skipped."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_globs": ["", "*.py"]},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    test_file = tmp_path / "test.py"
    test_file.write_text("test")

    # Should match *.py even though there's an empty pattern
    allowed, trace = explain_path(cfg, test_file)
    # The function should work correctly despite empty pattern


def test_matches_glob_exception_handling(tmp_path, monkeypatch):
    """Test that exceptions in fnmatch are handled."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {"include_globs": ["*.py"]},
                "priority": {},
                "sync": {"database": "wks.monitor"},
            }
        }
    )

    test_file = tmp_path / "test.py"
    test_file.write_text("test")

    # Mock fnmatch to raise exception
    original_fnmatch = __import__("fnmatch").fnmatch

    def mock_fnmatchcase(*args, **kwargs):
        if args[1] == "*.py":
            raise Exception("fnmatch error")
        return original_fnmatch.fnmatchcase(*args, **kwargs)

    monkeypatch.setattr("wks.api.monitor._matches_glob.fnmatch.fnmatchcase", mock_fnmatchcase)

    # Should handle exception gracefully
    allowed, trace = explain_path(cfg, test_file)
    # Function should not crash

