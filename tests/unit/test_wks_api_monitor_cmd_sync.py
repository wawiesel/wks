"""Tests for monitor cmd_sync API."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.monitor.cmd_sync import cmd_sync
from wks.utils.path_to_uri import path_to_uri


@pytest.mark.monitor
def test_monitor_cmd_sync_file(wks_home, minimal_config_dict):
    """Test syncing a single file."""
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "sync_me.txt"
    test_file.write_text("Sync Content", encoding="utf-8")

    # Must include the path to allow sync
    config = WKSConfig.load()
    config.monitor.filter.include_paths = [str(watch_dir)]
    config.save()

    res = run_cmd(cmd_sync, path=str(test_file))
    assert res.success is True
    assert res.output["files_synced"] == 1

    # Verify in DB
    with Database(config.database, "nodes") as db:
        doc = db.find_one({"local_uri": path_to_uri(test_file)})
        assert doc is not None
        assert doc["checksum"] is not None


@pytest.mark.monitor
def test_monitor_cmd_sync_directory_recursive(wks_home, minimal_config_dict):
    """Test syncing a directory recursively."""
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    (watch_dir / "sub").mkdir()
    (watch_dir / "f1.txt").write_text("f1")
    (watch_dir / "sub/f2.txt").write_text("f2")

    # Must include the path to allow sync
    config = WKSConfig.load()
    config.monitor.filter.include_paths = [str(watch_dir)]
    config.save()

    res = run_cmd(cmd_sync, path=str(watch_dir), recursive=True)
    assert res.success is True
    assert res.output["files_synced"] == 2


@pytest.mark.monitor
def test_monitor_cmd_sync_missing_path_removes_from_db(wks_home, minimal_config_dict):
    """Test that syncing a nonexistent path removes it from the DB."""
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "gone.txt"
    test_file.write_text("Temporary", encoding="utf-8")

    # 1. Sync it
    config = WKSConfig.load()
    config.monitor.filter.include_paths = [str(watch_dir)]
    config.save()
    run_cmd(cmd_sync, path=str(test_file))

    # 2. Delete it
    test_file.unlink()

    # 3. Sync missing path
    res = run_cmd(cmd_sync, path=str(test_file))
    assert res.success is True
    assert "Removed" in res.result

    # 4. Verify gone from DB
    with Database(config.database, "nodes") as db:
        doc = db.find_one({"local_uri": path_to_uri(test_file)})
        assert doc is None


@pytest.mark.monitor
def test_monitor_cmd_sync_skips_low_priority(wks_home, minimal_config_dict):
    """Test that sync skips files below min_priority."""
    # Set min_priority in config via WKSConfig
    config = WKSConfig.load()
    config.monitor.min_priority = 50.0
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)
    config.monitor.filter.include_paths = [str(watch_dir)]
    config.save()

    test_file = watch_dir / "low_priority.txt"
    test_file.write_text("Low Priority", encoding="utf-8")

    res = run_cmd(cmd_sync, path=str(test_file))
    assert res.success is True
    assert res.output["files_synced"] == 0
    assert res.output["files_skipped"] == 1


@pytest.mark.monitor
def test_monitor_cmd_sync_enforces_limit(wks_home, minimal_config_dict):
    """Test that sync enforces max_documents limit."""
    config = WKSConfig.load()
    config.monitor.max_documents = 2
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)
    config.monitor.filter.include_paths = [str(watch_dir)]
    config.save()

    (watch_dir / "1.txt").write_text("1")
    (watch_dir / "2.txt").write_text("2")
    (watch_dir / "3.txt").write_text("3")

    # Sync all 3
    run_cmd(cmd_sync, path=str(watch_dir), recursive=True)

    # Verify only 2 remain in DB (actually enforcing happens after sync)
    with Database(config.database, "nodes") as db:
        count = db.count_documents({"local_uri": {"$exists": True}})
        assert count <= 2
