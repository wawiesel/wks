from pathlib import Path

import pytest

from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def build_monitor_config(**overrides):
    config_dict = {
        "monitor": {
            "filter": {
                "include_paths": overrides.pop("include_paths", []),
                "exclude_paths": overrides.pop("exclude_paths", []),
                "include_dirnames": overrides.pop("include_dirnames", []),
                "exclude_dirnames": overrides.pop("exclude_dirnames", []),
                "include_globs": overrides.pop("include_globs", []),
                "exclude_globs": overrides.pop("exclude_globs", []),
            },
            "priority": overrides.pop(
                "priority",
                {
                    "dirs": {},
                    "weights": {
                        "depth_multiplier": 0.9,
                        "underscore_multiplier": 0.5,
                        "only_underscore_multiplier": 0.1,
                        "extension_weights": {},
                    },
                },
            ),
            "max_documents": overrides.pop("max_documents", 1000000),
            "min_priority": overrides.pop("min_priority", 0.0),
            "remote": {"mappings": []},
        }
    }
    return MonitorConfig.from_config_dict(config_dict)


def write_path(base: Path, relative_path: str, *, is_dir: bool = False) -> Path:
    target = base / relative_path
    if is_dir:
        target.mkdir(parents=True, exist_ok=True)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("test")
    return target


@pytest.mark.parametrize(
    ("config_kwargs", "relative_path", "is_dir", "expected_allowed", "expected_message"),
    [
        ({"include_paths": []}, "test.txt", False, False, "No include_paths defined"),
        ({"include_paths": ["include"]}, "include/test.txt", False, True, "Included by root"),
        ({"exclude_paths": ["exclude"]}, "exclude/test.txt", False, False, "Excluded by root"),
        ({"include_paths": ["include"]}, "other/test.txt", False, False, "Outside include_paths"),
        (
            {"include_paths": ["include"], "exclude_dirnames": ["node_modules"]},
            "include/node_modules/test.txt",
            False,
            False,
            "Parent dir 'node_modules' excluded",
        ),
        (
            {"include_paths": ["include"], "exclude_globs": ["*.tmp"]},
            "include/test.tmp",
            False,
            False,
            "Excluded by glob pattern",
        ),
        (
            {
                "include_paths": ["include"],
                "exclude_dirnames": ["node_modules"],
                "include_dirnames": ["node_modules"],
            },
            "include/node_modules/test.txt",
            False,
            True,
            "Parent dir 'node_modules' override",
        ),
        (
            {"include_paths": ["include"], "exclude_globs": ["*.tmp"], "include_globs": ["*.tmp"]},
            "include/test.tmp",
            False,
            True,
            "Included by glob override",
        ),
        (
            {"include_paths": ["include"], "exclude_dirnames": ["target_dir"]},
            "include/target_dir",
            True,
            False,
            "Directory 'target_dir' excluded",
        ),
    ],
)
def test_explain_path_filter_matrix(tmp_path, config_kwargs, relative_path, is_dir, expected_allowed, expected_message):
    resolved_kwargs = {}
    for key, value in config_kwargs.items():
        if isinstance(value, list):
            resolved_kwargs[key] = [
                str((tmp_path / item).resolve()) if key.endswith("paths") else item for item in value
            ]
        else:
            resolved_kwargs[key] = value

    target = write_path(tmp_path, relative_path, is_dir=is_dir)
    allowed, trace = explain_path(build_monitor_config(**resolved_kwargs), target)

    assert allowed is expected_allowed
    assert any(expected_message in message for message in trace)


def test_explain_path_wks_home_excluded(tmp_path, monkeypatch):
    wks_home = write_path(tmp_path, ".wks", is_dir=True)
    test_file = write_path(tmp_path, ".wks/test.txt")

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: wks_home))

    allowed, trace = explain_path(build_monitor_config(), test_file)
    assert allowed is False
    assert any("WKS home directory" in message for message in trace)


def test_explain_path_wks_home_equals_path(tmp_path, monkeypatch):
    wks_home = write_path(tmp_path, ".wks", is_dir=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: wks_home))

    allowed, trace = explain_path(build_monitor_config(), wks_home)
    assert allowed is False
    assert any("WKS home directory" in message for message in trace)


def test_explain_path_value_error_handling(tmp_path, monkeypatch):
    test_file = write_path(tmp_path, "test.txt")

    def mock_is_relative_to(self, *args, **kwargs):
        raise ValueError("Simulated Path Error")

    monkeypatch.setattr(Path, "is_relative_to", mock_is_relative_to)
    allowed, trace = explain_path(build_monitor_config(), test_file)

    assert allowed is False
    assert any("No include_paths defined" in message for message in trace)
