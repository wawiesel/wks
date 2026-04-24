import time

import pytest

from wks.api.config.normalize_path import normalize_path
from wks.api.config.URI import URI
from wks.api.daemon.Daemon import Daemon
from wks.api.database.Database import Database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.mongo,
]


def test_daemon_sync_creates_db_record(mongo_wks_env):
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running, "Daemon should start"

    try:
        time.sleep(2.0)

        test_file = watch_dir / "test_sync.txt"
        test_file.write_text("hello")

        time.sleep(3.0)

        db_name = "nodes"
        with Database(config.database, db_name) as db:
            record = db.find_one({"local_uri": str(URI.from_path(test_file))})
        assert record is not None, f"File should be in database: {test_file}"

    finally:
        daemon.stop()


def test_daemon_sync_removes_deleted_file(mongo_wks_env):
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    test_file = watch_dir / "to_delete.txt"
    test_file.write_text("will be deleted")

    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running

    try:
        time.sleep(2.0)

        from tests.conftest import run_cmd
        from wks.api.monitor.cmd_sync import cmd_sync

        sync_result = run_cmd(cmd_sync, URI.from_path(test_file))
        assert sync_result.success

        db_name = "nodes"
        with Database(config.database, db_name) as db:
            record = db.find_one({"local_uri": str(URI.from_path(test_file))})
            assert record is not None, "File should be in database before deletion"

        test_file.unlink()

        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, db_name) as db:
                record = db.find_one({"local_uri": str(URI.from_path(test_file))})
            if record is None:
                break
            if time.time() > deadline:
                raise AssertionError("Deleted file should be removed from database")
            time.sleep(0.5)  # Increased sleep interval for CI

    finally:
        daemon.stop()


def test_daemon_sync_handles_move(mongo_wks_env):
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    src_file = watch_dir / "original.txt"
    src_file.write_text("content")
    dst_file = watch_dir / "renamed.txt"

    daemon = Daemon()
    result = daemon.start(restrict_dir=watch_dir)
    assert result.running

    try:
        time.sleep(0.5)

        from tests.conftest import run_cmd
        from wks.api.monitor.cmd_sync import cmd_sync

        res = run_cmd(cmd_sync, URI.from_path(src_file))
        assert res.success, f"Sync failed: {res.output}"
        if res.output["files_synced"] != 1:
            print(f"DEBUG: Sync Output: {res.output}")
        assert res.output["files_synced"] == 1

        db_name = "nodes"
        with Database(config.database, db_name) as db:
            if db.find_one({"local_uri": str(URI.from_path(src_file))}) is None:
                print(f"DEBUG: DB docs: {list(db.find({}, {'local_uri': 1}))}")
                print(f"DEBUG: Looking for: {URI.from_path(src_file)!s}")
            assert db.find_one({"local_uri": str(URI.from_path(src_file))}) is not None

        src_file.rename(dst_file)

        time.sleep(1.5)

        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, db_name) as db:
                old_rec = db.find_one({"local_uri": str(URI.from_path(src_file))})
                new_rec = db.find_one({"local_uri": str(URI.from_path(dst_file))})
            if old_rec is None and new_rec is not None:
                break
            if time.time() > deadline:
                old_exists = old_rec is not None
                new_exists = new_rec is not None
                raise AssertionError(
                    f"Move did not reflect in DB in time. old={old_exists} new={new_exists}. "
                    f"Source path: {normalize_path(src_file).as_uri()}, Dest path: {normalize_path(dst_file).as_uri()}"
                )
            time.sleep(0.5)  # Increased sleep interval

    finally:
        daemon.stop()
