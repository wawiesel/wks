"""Integration tests for daemon-monitor sync with real MongoDB.

These tests REQUIRE `mongod` to be available. WKS will start it automatically
when `database.type="mongo"` and `database.data.local=true`, but the `mongod`
binary must exist on the system.
"""

import os
import shutil
import subprocess
import time

import pytest

from wks.api.config.WKSConfig import WKSConfig
from wks.api.daemon.Daemon import Daemon
from wks.api.database.Database import Database


def _mongod_available() -> bool:
    """Check if mongod is available and can be started."""
    if os.environ.get("WKS_TEST_MONGO_URI"):
        return True
    if not shutil.which("mongod"):
        return False
    # Try to connect to default port or check if we can start one
    try:
        result = subprocess.run(
            ["mongod", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# Mark all tests in this module
pytestmark = [
    pytest.mark.integration,
    pytest.mark.mongo,
]


@pytest.fixture
def mongo_wks_env(tmp_path, monkeypatch):
    """Set up WKS environment with real MongoDB."""
    from tests.conftest import minimal_config_dict

    if not _mongod_available():
        pytest.fail(
            "MongoDB tests require `mongod` in PATH. "
            "Install MongoDB so `mongod --version` works, or run without -m mongo."
        )

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    # Use a unique port to avoid conflicts with parallel test execution
    # Use tmp_path (unique per test) to generate a deterministic but unique port
    import hashlib
    import os
    import socket

    # Get worker ID from pytest-xdist if available
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
    worker_num = 0
    if worker_id.startswith("gw"):
        import contextlib

        with contextlib.suppress(ValueError):
            worker_num = int(worker_id[2:])

    # Use tmp_path to generate a unique but deterministic port per test
    # tmp_path is unique per test, so this ensures no collisions
    mongo_port = 27017  # Default valid port if using external URI
    external_uri = os.environ.get("WKS_TEST_MONGO_URI")

    if external_uri:
        mongo_uri = external_uri
        is_local = False
    else:
        path_hash = int(hashlib.md5(str(tmp_path).encode()).hexdigest()[:6], 16)
        pid = os.getpid()
        base_port = 27100
        # Each worker gets 10000 ports, use path hash and pid for uniqueness
        mongo_port = base_port + (worker_num * 10000) + (path_hash % 9000) + (pid % 100)

        # Verify port is actually available (in case of rare collision)
        max_attempts = 50
        original_port = mongo_port
        for attempt in range(max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", mongo_port))
                    break  # Port is available
                except OSError:
                    # Port in use, try next one in sequence
                    mongo_port = original_port + attempt
                    if mongo_port > 27999:
                        mongo_port = base_port + (attempt % 900)
        else:
            raise RuntimeError(f"Could not find available port after {max_attempts} attempts")

        mongo_uri = f"mongodb://127.0.0.1:{mongo_port}"
        is_local = True

    # Start with minimal config and override for MongoDB
    config_dict = minimal_config_dict()
    # Use Database context manager to start/manage mongod persistence
    # This prevents restarts inside the test loops which cause lock issues
    mongo_data_path = str(wks_home / "mongo-data")
    config_dict["database"] = {
        "type": "mongo",
        "prefix": "wks_test",
        "data": {
            "uri": mongo_uri,
            "local": is_local,
            "db_path": mongo_data_path,
            "port": mongo_port,
            "bind_ip": "127.0.0.1",
        },
    }
    config_dict["monitor"]["filter"]["include_paths"] = [str(watch_dir)]
    config_dict["daemon"]["sync_interval_secs"] = 0.1

    monkeypatch.setenv("WKS_HOME", str(wks_home))
    config = WKSConfig.model_validate(config_dict)
    config.save()

    # Start mongod once for the duration of the test
    # The Database context manager handles startup of local mongod
    from wks.api.database.Database import Database

    with Database(config.database, "setup") as db:
        # Verify connection
        db.get_client().server_info()

        yield {
            "wks_home": wks_home,
            "watch_dir": watch_dir,
            "config": config,
            "mongo_port": mongo_port,
        }

    # Context manager exit handles cleanup, but we can double check
    # to be safe for next tests
    try:
        daemon = Daemon()
        daemon.stop()
    except Exception:
        pass


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
        with Database(config.database, config.monitor.database) as db:
            record = db.find_one({"path": test_file.resolve().as_uri()})
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
        with Database(config.database, config.monitor.database) as db:
            record = db.find_one({"path": test_file.resolve().as_uri()})
            assert record is not None, "File should be in database before deletion"

        # Delete the file
        test_file.unlink()

        # Poll until removed (delete events can take a few cycles, especially in CI)
        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, config.monitor.database) as db:
                record = db.find_one({"path": test_file.resolve().as_uri()})
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

        run_cmd(cmd_sync, str(src_file))

        # Verify source is in DB
        with Database(config.database, config.monitor.database) as db:
            assert db.find_one({"path": src_file.resolve().as_uri()}) is not None

        # Move the file
        src_file.rename(dst_file)

        # Give daemon time to detect the move event (watchdog needs time to process)
        time.sleep(1.5)

        # Poll until old removed and new added (move events can take a few cycles, especially on slower CI)
        deadline = time.time() + 30.0  # Increased timeout for CI
        while True:
            with Database(config.database, config.monitor.database) as db:
                old_rec = db.find_one({"path": src_file.resolve().as_uri()})
                new_rec = db.find_one({"path": dst_file.resolve().as_uri()})
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
