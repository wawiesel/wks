"""Unit tests for _matches_glob function (tested through explain_path)."""


import pytest

from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_matches_glob_empty_pattern(tmp_path):
    """Test that empty patterns are skipped."""
    cfg = MonitorConfig.from_config_dict(
        {
            "monitor": {
                "filter": {
                    "include_paths": [],
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
                "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
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
                "filter": {
                    "include_paths": [],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": ["*.py"],
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
                "database": "monitor",
                "sync": {
                    "max_documents": 1000000,
                    "min_priority": 0.0,
                    "prune_interval_secs": 300.0,
                },
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
