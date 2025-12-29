"""Unit tests for transform cache prune and reset behavior."""

import json

import pytest

from tests.unit.conftest import run_cmd
from wks.api.database.cmd_prune import cmd_prune
from wks.api.database.cmd_reset import cmd_reset

pytestmark = pytest.mark.database


def test_reset_transform_clears_cache_files(monkeypatch, tmp_path, minimal_config_dict):
    """Reset transform database clears cache files."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create cache directory with some files
    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()
    (cache_dir / "abc123.md").write_text("cached content 1")
    (cache_dir / "def456.md").write_text("cached content 2")
    (cache_dir / "ghi789.txt").write_text("cached content 3")

    cfg = minimal_config_dict
    cfg["transform"]["cache"]["base_dir"] = str(cache_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # Verify files exist before reset
    assert (cache_dir / "abc123.md").exists()
    assert (cache_dir / "def456.md").exists()

    result = run_cmd(cmd_reset, database="transform")

    assert result.success

    # Cache files should be deleted
    assert not (cache_dir / "abc123.md").exists()
    assert not (cache_dir / "def456.md").exists()
    assert not (cache_dir / "ghi789.txt").exists()


def test_prune_transform_deletes_orphaned_files(monkeypatch, tmp_path, minimal_config_dict):
    """Prune transform deletes cache files not in database."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    # Create cache directory with orphaned file
    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()
    (cache_dir / "orphaned123.md").write_text("orphaned content")

    cfg = minimal_config_dict
    cfg["transform"]["cache"]["base_dir"] = str(cache_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # File exists but not in database
    assert (cache_dir / "orphaned123.md").exists()

    result = run_cmd(cmd_prune, database="transform")

    assert result.success

    # Orphaned file should be deleted
    assert not (cache_dir / "orphaned123.md").exists()
    assert result.output["deleted_count"] >= 1


def test_prune_transform_updates_timer(monkeypatch, tmp_path, minimal_config_dict):
    """Prune transform updates the prune timer."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cache_dir = tmp_path / "_transform"
    cache_dir.mkdir()

    cfg = minimal_config_dict
    cfg["transform"]["cache"]["base_dir"] = str(cache_dir)
    (wks_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # No timer before prune
    from wks.api.database.prune_timer import get_last_prune_timestamp

    assert get_last_prune_timestamp("transform") is None

    result = run_cmd(cmd_prune, database="transform")

    assert result.success

    # Timer should be set after prune
    timestamp = get_last_prune_timestamp("transform")
    assert timestamp is not None
