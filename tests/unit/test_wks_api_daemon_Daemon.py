"""Daemon filesystem event integration test (TDD scaffold)."""

import time

import pytest

from tests.unit.conftest import minimal_wks_config
from wks.api.daemon._read_status_file import read_status_file


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
    assert str(wks_home / "logs" / "daemon.log") == status.log_path


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
    d.start(restrict_dir=rdir1)
    status1 = read_status_file(wks_home)
    d.stop()
    d.start(restrict_dir=rdir2)
    status2 = read_status_file(wks_home)
    d.stop()

    assert status1["restrict_dir"] == str(rdir1)
    assert status2["restrict_dir"] == str(rdir2)
