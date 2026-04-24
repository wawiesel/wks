from pathlib import Path

import pytest

from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.matches_glob import matches_glob
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def test_matches_glob_empty_pattern(tmp_path):
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
                "remote": {"mappings": []},
            }
        }
    )

    test_file = tmp_path / "test.py"
    test_file.write_text("test")

    allowed, _trace = explain_path(cfg, test_file)
    assert allowed is True


def test_matches_glob_exception_propagates(monkeypatch):
    def mock_fnmatchcase(*args, **kwargs):
        raise ValueError("Simulated glob error")

    monkeypatch.setattr("fnmatch.fnmatchcase", mock_fnmatchcase)

    path = Path("/tmp/test.txt")
    with pytest.raises(ValueError, match="Simulated glob error"):
        matches_glob(["*.txt"], path)


def test_matches_glob_empty_pattern_in_list():
    path = Path("/tmp/test.txt")
    assert not matches_glob([""], path)
    assert matches_glob(["", "*.txt"], path)


def test_matches_glob_matches_by_filename_only():
    path = Path("dir/test.txt")
    assert matches_glob(["test.txt"], path) is True


def test_matches_glob_matches_by_path_only():
    path = Path("dir/test.txt")
    assert matches_glob(["dir/*.txt"], path) is True
