import json
import threading
import time
from unittest.mock import patch

import pytest

from tests.unit.conftest import minimal_wks_config
from wks.api.config.WKSConfig import WKSConfig
from wks.api.log.summarize_status_log_messages import STATUS_LOG_MESSAGE_LIMIT


def create_daemon(monkeypatch, tmp_path, *, sync_interval=None):
    from wks.api.daemon.Daemon import Daemon

    Daemon._global_instance = None
    config = minimal_wks_config()
    if sync_interval is not None:
        config.daemon.sync_interval_secs = sync_interval

    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    config.save()
    return Daemon(), wks_home


@pytest.mark.daemon
def test_daemon_starts_and_stops_cleanly(monkeypatch, tmp_path):
    daemon, wks_home = create_daemon(monkeypatch, tmp_path, sync_interval=0.05)
    restrict_dir = tmp_path / "xtest"
    restrict_dir.mkdir(parents=True, exist_ok=True)

    start_status = daemon.start(restrict_dir=restrict_dir)
    time.sleep(0.2)
    daemon.stop()

    assert start_status.running is True
    assert start_status.pid is not None
    assert (wks_home / "daemon.json").exists()
    assert not (wks_home / "daemon.lock").exists()


@pytest.mark.daemon
def test_daemon_prevents_double_start_and_reports_status(monkeypatch, tmp_path):
    daemon, _ = create_daemon(monkeypatch, tmp_path, sync_interval=0.05)
    restrict = tmp_path / "only"
    restrict.mkdir(parents=True, exist_ok=True)

    status = daemon.start(restrict_dir=restrict)
    live_status = daemon.status()

    assert status.running is True
    assert str(restrict) == live_status.restrict_dir
    assert str(WKSConfig.get_logfile_path()) == live_status.log_path
    with pytest.raises(RuntimeError):
        daemon.start()
    daemon.stop()


@pytest.mark.daemon
def test_daemon_writes_status_file(monkeypatch, tmp_path):
    daemon, wks_home = create_daemon(monkeypatch, tmp_path)
    restrict_dirs = [tmp_path / "r1", tmp_path / "r2"]
    for path in restrict_dirs:
        path.mkdir()

    daemon.start(restrict_dir=restrict_dirs[0])
    status1 = json.loads((wks_home / "daemon.json").read_text())
    daemon.stop()
    daemon.start(restrict_dir=restrict_dirs[1])
    status2 = json.loads((wks_home / "daemon.json").read_text())
    daemon.stop()

    assert status1["restrict_dir"] == str(restrict_dirs[0])
    assert status2["restrict_dir"] == str(restrict_dirs[1])


@pytest.mark.daemon
def test_daemon_status_file_summarizes_large_log_history(monkeypatch, tmp_path):
    daemon, wks_home = create_daemon(monkeypatch, tmp_path)
    warning_lines = [f"WARN: warn-{idx}" for idx in range(STATUS_LOG_MESSAGE_LIMIT + 6)]
    WKSConfig.get_logfile_path().write_text("\n".join(warning_lines) + "\n", encoding="utf-8")

    daemon.start()
    status = json.loads((wks_home / "daemon.json").read_text())
    daemon.stop()

    assert len(status["warnings"]) == STATUS_LOG_MESSAGE_LIMIT + 1
    assert "showing 20 most recent warnings out of 26 total" in status["warnings"][0]
    assert status["warnings"][1:] == warning_lines[-STATUS_LOG_MESSAGE_LIMIT:]


@pytest.mark.daemon
def test_daemon_foreground_coverage(mongo_wks_env):
    from wks.api.daemon.Daemon import Daemon

    daemon = Daemon()
    watch_dir = mongo_wks_env["watch_dir"]
    thread = threading.Thread(target=daemon.run_foreground, kwargs={"restrict_dir": watch_dir}, daemon=True)
    captured_handler = None

    def mock_signal(_sig, handler):
        nonlocal captured_handler
        captured_handler = handler

    with patch("signal.signal", side_effect=mock_signal):
        thread.start()
        time.sleep(2.0)
        test_file = watch_dir / "foreground_cov.txt"
        test_file.write_text("Public API Coverage", encoding="utf-8")
        time.sleep(1.0)
        test_file.unlink()
        time.sleep(1.0)
        if captured_handler:
            captured_handler(None, None)
        thread.join(timeout=5.0)

    assert not thread.is_alive()


def test_event_handler_logic():
    from wks.api.daemon._EventHandler import _EventHandler

    handler = _EventHandler()
    handler._modified.add("/path/modified.md")
    handler._created.add("/path/created.md")
    handler._deleted.add("/path/deleted.md")
    handler._moved["file:///old"] = "file:///new"

    events = handler.get_and_clear_events()
    assert "/path/modified.md" in events.modified
    assert "/path/created.md" in events.created
    assert "/path/deleted.md" in events.deleted
    assert ("file:///old", "file:///new") in events.moved
    assert len(handler.get_and_clear_events().modified) == 0


def test_sync_path_static_logic(monkeypatch, tmp_path, minimal_config_dict):
    from wks.api.daemon._sync_path_static import _sync_path_static

    wks_home = tmp_path / ".wks"
    wks_home.mkdir()
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    (wks_home / "config.json").write_text(json.dumps(minimal_config_dict), encoding="utf-8")

    logs: list[str] = []
    test_path = tmp_path / "test_dir"
    test_path.mkdir()
    _sync_path_static(test_path, tmp_path / "daemon.log", logs.append)
