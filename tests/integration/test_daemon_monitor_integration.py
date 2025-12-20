"""Integration tests for daemon-monitor sync with real MongoDB.

These tests REQUIRE `mongod` to be available. WKS will start it automatically
when `database.type="mongo"` and `database.data.local=true`, but the `mongod`
binary must exist on the system.
"""

import time

import pytest

from wks.api.daemon.Daemon import Daemon
from wks.api.database.Database import Database
from wks.utils.path_to_uri import path_to_uri

# Mark all tests in this module
pytestmark = [
    pytest.mark.integration,
    pytest.mark.mongo,
]


def test_daemon_sync_creates_db_record(mongo_wks_env):
    """Daemon should sync created files to MongoDB."""
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    # Start daemon
    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running, "Daemon should start"

    try:
        # Give daemon and local mongod time to initialize
        time.sleep(2.0)

        # Create a file
        test_file = watch_dir / "test_sync.txt"
        test_file.write_text("hello")

        # Wait for daemon to sync (sync_interval_secs = 0.1, plus margin for mongod startup)
        time.sleep(3.0)

        # Check database
        db_name = "nodes"
        with Database(config.database, db_name) as db:
            record = db.find_one({"local_uri": path_to_uri(test_file.resolve())})
        assert record is not None, f"File should be in database: {test_file}"

    finally:
        daemon.stop()


def test_daemon_sync_removes_deleted_file(mongo_wks_env):
    """Daemon should remove deleted files from MongoDB."""
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    # Create file first
    test_file = watch_dir / "to_delete.txt"
    test_file.write_text("will be deleted")

    # Start daemon
    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running

    try:
        time.sleep(0.5)

        # Manually sync the file first to ensure it's in DB
        from tests.conftest import run_cmd
        from wks.api.monitor.cmd_sync import cmd_sync

        sync_result = run_cmd(cmd_sync, str(test_file))
        assert sync_result.success

        # Verify it's in DB
        db_name = "nodes"
        with Database(config.database, db_name) as db:
            record = db.find_one({"local_uri": path_to_uri(test_file.resolve())})
            assert record is not None, "File should be in database before deletion"

        # Delete the file
        test_file.unlink()

        # Poll until removed (delete events can take a few cycles, especially in CI)
        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, db_name) as db:
                record = db.find_one({"local_uri": path_to_uri(test_file.resolve())})
            if record is None:
                break
            if time.time() > deadline:
                raise AssertionError("Deleted file should be removed from database")
            time.sleep(0.5)  # Increased sleep interval for CI

    finally:
        daemon.stop()


def test_daemon_sync_handles_move(mongo_wks_env):
    """Daemon should update database when file is moved."""
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    # Create source file
    src_file = watch_dir / "original.txt"
    src_file.write_text("content")
    dst_file = watch_dir / "renamed.txt"

    # Start daemon
    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running

    try:
        time.sleep(0.5)

        # Sync source file
        from tests.conftest import run_cmd
        from wks.api.monitor.cmd_sync import cmd_sync

        res = run_cmd(cmd_sync, str(src_file))
        assert res.success, f"Sync failed: {res.output}"
        if res.output["files_synced"] != 1:
            print(f"DEBUG: Sync Output: {res.output}")
        assert res.output["files_synced"] == 1

        # Verify source is in DB
        db_name = "nodes"
        with Database(config.database, db_name) as db:
            if db.find_one({"local_uri": path_to_uri(src_file.resolve())}) is None:
                print(f"DEBUG: DB docs: {list(db.find({}, {'local_uri': 1}))}")
                print(f"DEBUG: Looking for: {path_to_uri(src_file.resolve())}")
            assert db.find_one({"local_uri": path_to_uri(src_file.resolve())}) is not None

        # Move the file
        src_file.rename(dst_file)

        # Give daemon time to detect the move event (watchdog needs time to process)
        time.sleep(1.5)

        # Poll until old removed and new added (move events can take a few cycles, especially on slower CI)
        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, db_name) as db:
                old_rec = db.find_one({"local_uri": path_to_uri(src_file.resolve())})
                new_rec = db.find_one({"local_uri": path_to_uri(dst_file.resolve())})
            if old_rec is None and new_rec is not None:
                break
            if time.time() > deadline:
                # More detailed error message
                old_exists = old_rec is not None
                new_exists = new_rec is not None
                raise AssertionError(
                    f"Move did not reflect in DB in time. old={old_exists} new={new_exists}. "
                    f"Source path: {src_file.resolve().as_uri()}, Dest path: {dst_file.resolve().as_uri()}"
                )
            time.sleep(0.5)  # Increased sleep interval

    finally:
        daemon.stop()
