"""Integration tests for background daemon loop via cmd_start."""

import time

import pytest

from tests.unit.conftest import run_cmd
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_stop import cmd_stop
from wks.api.database.Database import Database
from wks.api.URI import URI


@pytest.mark.daemon
def test_daemon_background_watch_restrict(mongo_wks_env):
    """Test that background daemon processes events in a restricted directory."""
    wks_home = mongo_wks_env["wks_home"]
    watch_dir = mongo_wks_env["watch_dir"]
    config = mongo_wks_env["config"]

    # Start daemon restricted to watch_dir
    res = run_cmd(cmd_start, restrict_dir=watch_dir)
    assert res.success is True

    try:
        # GIVE DAEMON TIME TO START OBSERVER
        time.sleep(2.0)

        # Create a file in watch_dir
        test_file = watch_dir / "test.txt"
        test_file.write_text("Hello Daemon", encoding="utf-8")
        test_uri = str(URI.from_path(test_file))

        deadline = time.time() + 15.0
        found = False
        last_doc = None
        while time.time() < deadline:
            with Database(config.database, "nodes") as db:
                doc = db.find_one({"local_uri": test_uri})
                if doc:
                    found = True
                    break
                if time.time() > (deadline - 2.0):
                    last_doc = list(db.find({}))
            time.sleep(0.5)

        if not found:
            log_path = wks_home / "logfile"
            log_content = log_path.read_text() if log_path.exists() else "NO LOG FILE"
            pytest.fail(
                f"Daemon did not sync the new file to the database.\n"
                f"Target URI: {test_uri}\n"
                f"Existing docs in 'nodes': {last_doc}\n"
                f"Log Content:\n{log_content}"
            )

        # Give it a moment before deletion
        time.sleep(1.0)

        # Test deletion
        test_file.unlink()

        deadline = time.time() + 10.0
        deleted = False
        while time.time() < deadline:
            with Database(config.database, "nodes") as db:
                doc = db.find_one({"local_uri": test_uri})
                if not doc:
                    deleted = True
                    break
            time.sleep(0.5)

        assert deleted, "Daemon did not sync the deletion to the database"

    finally:
        run_cmd(cmd_stop)


@pytest.mark.daemon
def test_daemon_ignore_internal_files(mongo_wks_env):
    """Test that daemon ignores changes to its own logs, lock, and status files."""
    wks_home = mongo_wks_env["wks_home"]

    # Start daemon watching WKS_HOME
    res = run_cmd(cmd_start, restrict_dir=wks_home)
    assert res.success is True

    try:
        # Wait for iteration
        time.sleep(2.0)

        log_path = wks_home / "logfile"
        assert log_path.exists()

        # Verify it didn't sync internal files to 'nodes'
        config = mongo_wks_env["config"]
        with Database(config.database, "nodes") as db:
            daemon_json_uri = str(URI.from_path(wks_home / "daemon.json"))
            logfile_uri = str(URI.from_path(wks_home / "logfile"))

            assert db.find_one({"local_uri": daemon_json_uri}) is None
            assert db.find_one({"local_uri": logfile_uri}) is None

    finally:
        run_cmd(cmd_stop)


@pytest.mark.daemon
def test_cmd_start_already_running(mongo_wks_env):
    """Test starting daemon when it is already running."""
    # 1. Start it
    res1 = run_cmd(cmd_start)
    assert res1.success is True
    assert res1.output["running"] is True

    try:
        # 2. Try starting again
        res2 = run_cmd(cmd_start)
        assert res2.success is False
        assert "already running" in res2.result.lower() or "error" in res2.result.lower()
        assert res2.output["running"] is True
    finally:
        run_cmd(cmd_stop)


@pytest.mark.daemon
def test_cmd_start_blocking(mongo_wks_env):
    """Test cmd_start with blocking=True."""
    import threading

    # We call cmd_start(blocking=True) in a thread because it blocks
    # We'll use a local instance to avoid side effects on the fixture daemon if any

    def run_blocking():
        run_cmd(cmd_start, blocking=True)

    t = threading.Thread(target=run_blocking)
    t.daemon = True

    # We need to capture the signal handler to stop it
    from unittest.mock import patch

    captured_handler = None

    def mock_signal(sig, handler):
        nonlocal captured_handler
        captured_handler = handler

    with patch("signal.signal", side_effect=mock_signal):
        t.start()
        time.sleep(1.0)

        # Verify it's running (lock file)
        wks_home = mongo_wks_env["wks_home"]
        assert (wks_home / "daemon.lock").exists()

        # Stop it
        if captured_handler:
            captured_handler(None, None)

        t.join(timeout=5.0)
        assert not t.is_alive()
