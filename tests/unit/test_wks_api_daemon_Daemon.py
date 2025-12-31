"""Daemon filesystem event integration test (TDD scaffold)."""

import json
import time

import pytest

from tests.unit.conftest import minimal_wks_config
from wks.api.config.WKSConfig import WKSConfig


@pytest.mark.daemon
def test_daemon_starts_and_stops_cleanly(monkeypatch, tmp_path):
    """Test that daemon starts, runs, and stops without error.

    Note: Filesystem events are synced to monitor database via subprocess,
    not returned via get_filesystem_events(). See test_wks_api_daemon_monitor_sync.py
    for integration tests of event syncing.
    """
    from wks.api.daemon.Daemon import Daemon

    Daemon._global_instance = None

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05

    # Set WKS_HOME and persist config (daemon will load WKSConfig from disk)
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Restrict to a temp directory
    rdir = tmp_path / "xtest"
    rdir.mkdir(parents=True, exist_ok=True)

    d = Daemon()
    start_status = d.start(restrict_dir=rdir)
    assert start_status.running is True
    assert start_status.pid is not None

    # Give daemon time to initialize
    time.sleep(0.2)

    # Verify status file was written
    status_file = wks_home / "daemon.json"
    assert status_file.exists(), "daemon.json should be created"

    # Stop cleanly
    d.stop()

    # Verify lock file is removed
    lock_file = wks_home / "daemon.lock"
    assert not lock_file.exists(), "daemon.lock should be removed after stop"


@pytest.mark.daemon
def test_daemon_prevents_double_start(monkeypatch, tmp_path):
    from wks.api.daemon.Daemon import Daemon

    Daemon._global_instance = None

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    d = Daemon()
    status1 = d.start()
    assert status1.running is True
    with pytest.raises(RuntimeError):
        d.start()
    d.stop()


@pytest.mark.daemon
def test_daemon_status_includes_restrict_and_log(monkeypatch, tmp_path):
    from wks.api.daemon.Daemon import Daemon

    Daemon._global_instance = None

    cfg = minimal_wks_config()
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    restrict = tmp_path / "only"
    restrict.mkdir(parents=True, exist_ok=True)

    d = Daemon()
    d.start(restrict_dir=restrict)
    status = d.status()
    d.stop()

    assert str(restrict) == status.restrict_dir
    assert str(WKSConfig.get_logfile_path()) == status.log_path


@pytest.mark.daemon
def test_daemon_writes_status_file(monkeypatch, tmp_path):
    from wks.api.daemon.Daemon import Daemon

    Daemon._global_instance = None

    cfg = minimal_wks_config()
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    rdir1 = tmp_path / "r1"
    rdir2 = tmp_path / "r2"
    rdir1.mkdir()
    rdir2.mkdir()

    d = Daemon()
    d = Daemon()
    d.start(restrict_dir=rdir1)
    status1 = json.loads((wks_home / "daemon.json").read_text())
    d.stop()
    d.start(restrict_dir=rdir2)
    status2 = json.loads((wks_home / "daemon.json").read_text())
    d.stop()

    assert status1["restrict_dir"] == str(rdir1)
    assert status2["restrict_dir"] == str(rdir2)


@pytest.mark.daemon
def test_daemon_foreground_coverage(mongo_wks_env):
    """Call Daemon.run_foreground in a thread to capture coverage via public API."""
    import threading
    from unittest.mock import patch

    watch_dir = mongo_wks_env["watch_dir"]

    from wks.api.daemon.Daemon import Daemon

    daemon = Daemon()

    # We'll use a thread to run the blocking foreground loop
    t = threading.Thread(target=daemon.run_foreground, kwargs={"restrict_dir": watch_dir})
    t.daemon = True

    captured_handler = None

    def mock_signal(sig, handler):
        nonlocal captured_handler
        captured_handler = handler

    with patch("signal.signal", side_effect=mock_signal):
        t.start()
        time.sleep(2.0)

        test_file = watch_dir / "foreground_cov.txt"
        test_file.write_text("Public API Coverage", encoding="utf-8")
        time.sleep(1.0)
        test_file.unlink()
        time.sleep(1.0)

        if captured_handler:
            captured_handler(None, None)

        t.join(timeout=5.0)
        assert not t.is_alive()


def test_event_handler_logic():
    """Test accumulating and clearing events (logic from _EventHandler)."""
    from wks.api.daemon._EventHandler import _EventHandler

    handler = _EventHandler()

    # Manually add events
    handler._modified.add("/path/modified.md")
    handler._created.add("/path/created.md")
    handler._deleted.add("/path/deleted.md")
    handler._moved["file:///old"] = "file:///new"

    events = handler.get_and_clear_events()

    assert "/path/modified.md" in events.modified
    assert "/path/created.md" in events.created
    assert "/path/deleted.md" in events.deleted
    assert ("file:///old", "file:///new") in events.moved

    # Verify cleared
    events2 = handler.get_and_clear_events()
    assert len(events2.modified) == 0


def test_sync_path_static_logic(monkeypatch, tmp_path, minimal_config_dict):
    """Test sync_path_static logic (private utility used by daemon)."""
    from wks.api.daemon._sync_path_static import _sync_path_static

    # Setup config
    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    log_file = tmp_path / "daemon.log"
    test_path = tmp_path / "test_dir"
    test_path.mkdir()

    logs = []

    def log_fn(msg: str) -> None:
        logs.append(msg)

    _sync_path_static(test_path, log_file, log_fn)
    # Should complete without error
