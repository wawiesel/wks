"""Integration-ish tests for wks.api.daemon.cmd_start without mocks."""

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.daemon import cmd_start, cmd_stop


@pytest.mark.daemon
def test_cmd_start_creates_artifacts(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    restrict = tmp_path / "watch"
    restrict.mkdir(parents=True, exist_ok=True)

    start_result = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert start_result.success is True
    assert start_result.output["running"] is True

    # Artifacts should exist
    assert (wks_home / "daemon.json").exists()
    assert (wks_home / "logs" / "daemon.log").exists()
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop.cmd_stop)
    assert stop_result.success is True
    assert stop_result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()


@pytest.mark.daemon
def test_cmd_start_twice_emits_warning(monkeypatch, tmp_path):
    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    restrict = tmp_path / "watch"
    restrict.mkdir(parents=True, exist_ok=True)

    first = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert first.success is True
    assert first.output["running"] is True

    # Give daemon subprocess a moment to start and be observable via PID.
    import os
    import time

    lock_path = wks_home / "daemon.lock"
    deadline = time.time() + 2.0
    while True:
        if lock_path.exists():
            try:
                pid = int(lock_path.read_text().strip() or "0")
                if pid > 0:
                    os.kill(pid, 0)
                    break
            except Exception:
                pass
        if time.time() > deadline:
            raise AssertionError("Daemon subprocess did not appear to be running in time")
        time.sleep(0.05)

    # Second start must fail (per spec) but daemon remains running
    second = run_cmd(cmd_start.cmd_start, restrict_dir=restrict)
    assert second.success is False
    assert second.output["running"] is True

    log_path = wks_home / "logs" / "daemon.log"
    log_text = log_path.read_text()
    assert "ERROR: Daemon already running" in log_text
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop.cmd_stop)
    assert stop_result.success is True
    assert stop_result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()
