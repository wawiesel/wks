"""Daemon filesystem event integration test (TDD scaffold)."""

import platform
import time
from pathlib import Path

import pytest

from wks.api.daemon._read_status_file import read_status_file
from tests.unit.conftest import minimal_wks_config


@pytest.mark.daemon
def test_daemon_reports_fs_events(monkeypatch, tmp_path):
    from wks.api.daemon import Daemon
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

    # TDD target API for Daemon (to be implemented):
    # - Daemon() loads WKSConfig from WKS_HOME internally (no config passed to ctor)
    # - start(restrict_dir: Path | None) starts background watcher (single instance)
    # - status() returns object with running/pid/log_path
    # - get_filesystem_events() returns and clears accumulated events
    # - stop() stops the watcher
    from wks.api.daemon import Daemon  # noqa: WPS433 (import for TDD target)

    d = Daemon()
    start_status = d.start(restrict_dir=rdir)
    assert start_status.running is True

    # Trigger filesystem events
    f1 = rdir / "touch.txt"
    f1.write_text("hello")
    time.sleep(0.1)
    f1.write_text("world")  # modify
    time.sleep(0.1)
    f2 = rdir / "move_me.txt"
    f2.write_text("move")
    time.sleep(0.1)
    f2_renamed = rdir / "moved.txt"
    f2.rename(f2_renamed)  # move
    time.sleep(0.1)
    f1.unlink()  # delete
    time.sleep(0.2)

    events = d.get_filesystem_events()
    d.stop()
    print(events)
    # Validate event contents
    assert events is not None
    assert str(f1) in events.created
    assert str(f1) in events.deleted
    assert (str(f2), str(f2_renamed)) in [(old, new) for old, new in events.moved]
    all_paths = (
        events.modified
        + events.created
        + events.deleted
        + [p for old, new in events.moved for p in (old, new)]
    )
    assert all(str(p).startswith(str(rdir)) for p in all_paths)


@pytest.mark.daemon
def test_daemon_prevents_double_start(monkeypatch, tmp_path):
    from wks.api.daemon import Daemon
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
    status2 = d.start()
    assert status2.running is True  # second start returns existing running
    d.stop()


@pytest.mark.daemon
def test_daemon_status_includes_restrict_and_log(monkeypatch, tmp_path):
    from wks.api.daemon import Daemon
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
    assert str(wks_home / "logs" / "daemon.log") == status.log_path


@pytest.mark.daemon
def test_daemon_writes_status_file(monkeypatch, tmp_path):
    from wks.api.daemon import Daemon
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
    d.start(restrict_dir=rdir1)
    status1 = read_status_file(wks_home)
    d.stop()
    d.start(restrict_dir=rdir2)
    status2 = read_status_file(wks_home)
    d.stop()

    assert status1["restrict_dir"] == str(rdir1)
    assert status2["restrict_dir"] == str(rdir2)
