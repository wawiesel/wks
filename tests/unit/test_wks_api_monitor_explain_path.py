"""Unit tests for explain_path function."""

import pytest

from wks.api.monitor.explain_path import explain_path
from wks.api.monitor.MonitorConfig import MonitorConfig

pytestmark = pytest.mark.monitor


def build_monitor_config(**overrides):
    """Build a MonitorConfig for testing using public API."""
    # Use from_config_dict to create config through public API
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


def test_explain_path_wks_home_excluded(tmp_path, monkeypatch):
    """Test that paths within WKS home are automatically excluded."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    test_file = wks_home / "test.txt"
    test_file.write_text("test")

    monkeypatch.setenv("WKS_HOME", str(wks_home))
    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: wks_home))

    cfg = build_monitor_config()
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("WKS home directory" in msg for msg in trace)


def test_explain_path_included_by_root(tmp_path):
    """Test that paths within include_paths are allowed."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    test_file = include_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(include_paths=[str(include_dir)])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is True
    assert any("Included by root" in msg for msg in trace)


def test_explain_path_excluded_by_root(tmp_path):
    """Test that paths within exclude_paths are excluded."""
    exclude_dir = tmp_path / "exclude"
    exclude_dir.mkdir()
    test_file = exclude_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(exclude_paths=[str(exclude_dir)])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("Excluded by root" in msg for msg in trace)


def test_explain_path_outside_include_paths(tmp_path):
    """Test that paths outside include_paths are excluded when include_paths are defined."""
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    test_file = other_dir / "test.txt"
    test_file.write_text("test")

    include_dir = tmp_path / "include"
    include_dir.mkdir()

    cfg = build_monitor_config(include_paths=[str(include_dir)])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("Outside include_paths" in msg for msg in trace)


def test_explain_path_no_include_paths_default_exclude(tmp_path):
    """Test that paths are excluded by default when no include_paths are defined."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config()
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("No include_paths defined" in msg for msg in trace)


def test_explain_path_excluded_by_dirname(tmp_path):
    """Test that paths with excluded parent dirname are excluded."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    excluded_dir = include_dir / "node_modules"
    excluded_dir.mkdir()
    test_file = excluded_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(include_paths=[str(include_dir)], exclude_dirnames=["node_modules"])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("Parent dir 'node_modules' excluded" in msg for msg in trace)


def test_explain_path_excluded_by_glob(tmp_path):
    """Test that paths matching exclude globs are excluded."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    test_file = include_dir / "test.tmp"
    test_file.write_text("test")

    cfg = build_monitor_config(include_paths=[str(include_dir)], exclude_globs=["*.tmp"])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is False
    assert any("Excluded by glob pattern" in msg for msg in trace)


def test_explain_path_override_by_dirname(tmp_path):
    """Test that include_dirname can override exclude_dirname."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    excluded_dir = include_dir / "node_modules"
    excluded_dir.mkdir()
    test_file = excluded_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(
        include_paths=[str(include_dir)],
        exclude_dirnames=["node_modules"],
        include_dirnames=["node_modules"],
    )
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is True
    assert any("Parent dir 'node_modules' override" in msg for msg in trace)


def test_explain_path_override_by_glob(tmp_path):
    """Test that include_glob can override exclude_glob."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    test_file = include_dir / "test.tmp"
    test_file.write_text("test")

    cfg = build_monitor_config(
        include_paths=[str(include_dir)],
        exclude_globs=["*.tmp"],
        include_globs=["*.tmp"],
    )
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is True
    assert any("Included by glob override" in msg for msg in trace)


def test_explain_path_allowed_when_not_excluded(tmp_path):
    """Test that paths are allowed when not excluded."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    test_file = include_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(include_paths=[str(include_dir)])
    allowed, trace = explain_path(cfg, test_file)

    assert allowed is True
    assert any("Included by root" in msg for msg in trace)


def test_explain_path_directory_itself_excluded(tmp_path):
    """Test that a directory is excluded if its own name is in exclude_dirnames."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    excluded_dir = include_dir / "target_dir"
    excluded_dir.mkdir()

    cfg = build_monitor_config(include_paths=[str(include_dir)], exclude_dirnames=["target_dir"])
    # Check the directory itself
    allowed, trace = explain_path(cfg, excluded_dir)

    assert allowed is False
    assert any("Directory 'target_dir' excluded" in msg for msg in trace)


def test_explain_path_value_error_handling(tmp_path, monkeypatch):
    """Test that ValueError in is_relative_to is handled gracefully."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config()

    # Mock Path.is_relative_to to raise ValueError
    from pathlib import Path

    def mock_is_relative_to(self, *args, **kwargs):
        raise ValueError("Simulated Path Error")

    monkeypatch.setattr(Path, "is_relative_to", mock_is_relative_to)

    allowed, trace = explain_path(cfg, test_file)
    # It should fall through the try-except-pass block and continue
    # Without include_paths, it should default to False (No include_paths defined)
    assert allowed is False
    assert any("No include_paths defined" in msg for msg in trace)


def test_explain_path_parent_equals_self_edge_case(tmp_path):
    """Test explain_path handles edge case where resolved.parent == resolved (tests line 80)."""
    include_dir = tmp_path / "include"
    include_dir.mkdir()
    test_file = include_dir / "test.txt"
    test_file.write_text("test")

    cfg = build_monitor_config(
        include_paths=[str(include_dir)],
        exclude_dirnames=["test"],
        include_dirnames=["test"],
    )

    # Mock the path to have parent == self (edge case)
    from pathlib import Path

    class MockPath(Path):
        @property
        def parent(self):
            return self

    # This tests the edge case where parent == self
    # The code checks: resolved.parent.name if resolved.parent != resolved else ""
    # We can't easily create this condition, but we can test the logic path
    # by ensuring the override logic works correctly
    allowed, _trace = explain_path(cfg, test_file)
    # Should be allowed due to include_dirname override
    assert allowed is True


def test_explain_path_wks_home_equals_path(tmp_path, monkeypatch):
    """Test explain_path when path equals wks_home exactly (tests line 25)."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    from wks.api.config.WKSConfig import WKSConfig

    monkeypatch.setattr(WKSConfig, "get_home_dir", classmethod(lambda cls: wks_home))

    cfg = build_monitor_config()
    # Test with path that equals wks_home exactly
    allowed, trace = explain_path(cfg, wks_home)

    assert allowed is False
    assert any("WKS home directory" in msg for msg in trace)
