"""Tests for monitor cmd_sync API."""

from pathlib import Path

import pytest

from tests.unit.conftest import run_cmd
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.monitor.cmd_sync import cmd_sync
from wks.api.URI import URI
from wks.utils.path_to_uri import path_to_uri


@pytest.mark.monitor
def test_monitor_cmd_sync_file(wks_home, minimal_config_dict):
    """Test syncing a single file.

    Requirements:
    - MON-001
    - MON-005
    """
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "sync_me.txt"
    test_file.write_text("Sync Content", encoding="utf-8")

    # Must include the path to allow sync
    config = WKSConfig.load()
    config.monitor.filter.include_paths.append(str(watch_dir))
    config.save()

    res = run_cmd(cmd_sync, uri=URI.from_path(test_file))
    assert res.success is True
    assert res.output["files_synced"] == 1

    # Verify in DB
    with Database(config.database, "nodes") as db:
        doc = db.find_one({"local_uri": path_to_uri(test_file)})
        assert doc is not None
        assert doc["checksum"] is not None


@pytest.mark.monitor
def test_monitor_cmd_sync_directory_recursive(wks_home, minimal_config_dict):
    """Test syncing a directory recursively.

    Requirements:
    - MON-001
    - MON-005
    """
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    (watch_dir / "sub").mkdir()
    (watch_dir / "f1.txt").write_text("f1")
    (watch_dir / "sub/f2.txt").write_text("f2")

    # Must include the path to allow sync
    config = WKSConfig.load()
    config.monitor.filter.include_paths.append(str(watch_dir))
    config.save()

    res = run_cmd(cmd_sync, uri=URI.from_path(watch_dir), recursive=True)
    assert res.success is True
    assert res.output["files_synced"] == 2


@pytest.mark.monitor
def test_monitor_cmd_sync_missing_path_removes_from_db(wks_home, minimal_config_dict):
    """Test that syncing a nonexistent path removes it from the DB.

    Requirements:
    - MON-001
    - MON-005
    """
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    test_file = watch_dir / "gone.txt"
    test_file.write_text("Temporary", encoding="utf-8")

    # 1. Sync it
    config = WKSConfig.load()
    config.monitor.filter.include_paths.append(str(watch_dir))
    config.save()
    run_cmd(cmd_sync, uri=URI.from_path(test_file))

    # 2. Delete it
    test_file.unlink()

    # 3. Sync missing path
    res = run_cmd(cmd_sync, uri=URI.from_path(test_file))
    assert res.success is True
    assert "Removed" in res.result

    # 4. Verify gone from DB
    with Database(config.database, "nodes") as db:
        doc = db.find_one({"local_uri": path_to_uri(test_file)})
        assert doc is None


@pytest.mark.monitor
def test_monitor_cmd_sync_skips_low_priority(wks_home, minimal_config_dict):
    """Test that sync skips files below min_priority.

    Requirements:
    - MON-001
    - MON-005
    """
    # Set min_priority in config via WKSConfig
    config = WKSConfig.load()
    config.monitor.min_priority = 50.0
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)
    config.monitor.filter.include_paths.append(str(watch_dir))
    config.save()

    test_file = watch_dir / "low_priority.txt"
    test_file.write_text("Low Priority", encoding="utf-8")

    res = run_cmd(cmd_sync, uri=URI.from_path(test_file))
    assert res.success is True
    assert res.output["files_synced"] == 0
    assert res.output["files_skipped"] == 1


@pytest.mark.monitor
def test_monitor_cmd_sync_enforces_limit(tracked_wks_config, wks_home):
    """Test that sync enforces max_documents limit.

    Requirements:
    - MON-001
    - MON-005
    """
    tracked_wks_config.monitor.max_documents = 2
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)
    tracked_wks_config.monitor.filter.include_paths.append(str(watch_dir))

    # Create 3 files with explicit priorities
    with Database(tracked_wks_config.database, "nodes") as db:
        db.insert_one({"local_uri": "file:///low", "priority": 1.0, "checksum": "abc"})
        db.insert_one({"local_uri": "file:///mid", "priority": 2.0, "checksum": "def"})
        db.insert_one({"local_uri": "file:///high", "priority": 100.0, "checksum": "ghi"})

    test_file = watch_dir / "1.txt"
    test_file.write_text("1")

    # Mock calculate_priority to return high value for 1.txt
    from unittest.mock import patch

    with patch("wks.api.monitor.cmd_sync.calculate_priority", return_value=200.0):
        # Run sync to trigger enforcement
        res = run_cmd(cmd_sync, uri=URI.from_path(test_file))
        assert res.success is True

    # Verify only 2 remain and 'low' and 'mid' are gone
    with Database(tracked_wks_config.database, "nodes") as db:
        count = db.count_documents({"doc_type": {"$ne": "meta"}})
        assert count <= 2
        assert db.find_one({"local_uri": "file:///low"}) is None
        assert db.find_one({"local_uri": "file:///mid"}) is None
        assert db.find_one({"local_uri": "file:///high"}) is not None


@pytest.mark.monitor
def test_monitor_cmd_sync_loop_exception(wks_home, minimal_config_dict):
    """Trigger exception in monitor sync loop via permission error.

    Requirements:
    - MON-001
    - MON-008
    """
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    unreadable = watch_dir / "unreadable.txt"
    unreadable.write_text("Secret", encoding="utf-8")
    unreadable.chmod(0o000)

    try:
        config = WKSConfig.load()
        config.monitor.filter.include_paths.append(str(watch_dir))
        config.save()

        res = run_cmd(cmd_sync, uri=URI.from_path(watch_dir), recursive=True)
        assert res.success is False
        assert len(res.output["errors"]) == 1
        assert "unreadable.txt" in res.output["errors"][0]
    finally:
        unreadable.chmod(0o644)


@pytest.mark.monitor
def test_monitor_cmd_sync_skips_excluded_file(wks_home, minimal_config_dict):
    """Test that sync skips files excluded by monitor rules (hits line 110-115).

    Requirements:
    - MON-001
    - MON-005
    """
    watch_dir = Path(str(wks_home) + "_watched")
    watch_dir.mkdir(parents=True, exist_ok=True)

    config = WKSConfig.load()
    config.monitor.filter.include_paths.append(str(watch_dir))
    # Exclude .tmp files
    config.monitor.filter.exclude_globs = ["*.tmp"]
    config.save()

    test_file = watch_dir / "skip_me.tmp"
    test_file.write_text("Temp Data", encoding="utf-8")

    res = run_cmd(cmd_sync, uri=URI.from_path(test_file))
    assert res.success is True
    assert res.output["files_synced"] == 0
    assert res.output["files_skipped"] == 1
