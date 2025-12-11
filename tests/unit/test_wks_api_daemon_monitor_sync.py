"""Integration test: daemon events trigger monitor sync."""

import time
from pathlib import Path

import pytest

from wks.api.daemon import Daemon
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from tests.unit.conftest import minimal_wks_config


@pytest.mark.daemon
def test_daemon_triggers_monitor_sync(monkeypatch, tmp_path):
    """Ensure daemon filesystem events lead to monitor sync records."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    cfg.monitor.filter.include_paths = [str(watch_dir)]
    cfg.save()

    daemon = Daemon()
    try:
        start_status = daemon.start(restrict_dir=watch_dir)
        assert start_status.running is True

        target_file = watch_dir / "file.txt"
        target_file.write_text("hello", encoding="utf-8")

        # Allow watchdog to observe and sync
        time.sleep(0.3)

        # Verify monitor database has the file entry
        config = WKSConfig.load()
        with Database(config.database, config.monitor.database) as database:
            doc = database.find_one({"path": target_file.resolve().as_uri()})
        assert doc is not None
    finally:
        daemon.stop()


@pytest.mark.daemon
def test_daemon_moves_remove_source(monkeypatch, tmp_path):
    """Moving a file should remove source and add destination in monitor DB."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    cfg.monitor.filter.include_paths = [str(watch_dir)]
    cfg.save()

    daemon = Daemon()
    try:
        start_status = daemon.start(restrict_dir=watch_dir)
        assert start_status.running is True

        src = watch_dir / "move_me.txt"
        dst = watch_dir / "moved.txt"
        src.write_text("hello", encoding="utf-8")
        time.sleep(0.2)

        src.rename(dst)
        time.sleep(0.3)

        config = WKSConfig.load()
        with Database(config.database, config.monitor.database) as database:
            assert database.find_one({"path": src.resolve().as_uri()}) is None
            assert database.find_one({"path": dst.resolve().as_uri()}) is not None
    finally:
        daemon.stop()


@pytest.mark.daemon
def test_daemon_deletes_remove_from_monitor(monkeypatch, tmp_path):
    """Deleting a file should remove it from the monitor DB."""
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    watch_dir = tmp_path / "watched"
    watch_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("WKS_HOME", str(wks_home))

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    cfg.monitor.filter.include_paths = [str(watch_dir)]
    cfg.save()

    daemon = Daemon()
    try:
        start_status = daemon.start(restrict_dir=watch_dir)
        assert start_status.running is True

        target = watch_dir / "delete_me.txt"
        target.write_text("bye", encoding="utf-8")
        time.sleep(0.2)

        target.unlink()
        time.sleep(0.3)

        config = WKSConfig.load()
        with Database(config.database, config.monitor.database) as database:
            assert database.find_one({"path": target.resolve().as_uri()}) is None
    finally:
        daemon.stop()
