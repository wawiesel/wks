"""Integration-ish tests for wks.api.daemon.cmd_start without mocks."""

import pytest

from tests.unit.conftest import minimal_wks_config, run_cmd
from wks.api.daemon.cmd_start import cmd_start
from wks.api.daemon.cmd_stop import cmd_stop


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

    start_result = run_cmd(cmd_start, restrict_dir=restrict)
    assert start_result.success is True
    assert start_result.output["running"] is True

    # Artifacts should exist
    assert (wks_home / "daemon.json").exists()
    assert (wks_home / "logfile").exists()
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop)
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

    first = run_cmd(cmd_start, restrict_dir=restrict)
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
    second = run_cmd(cmd_start, restrict_dir=restrict)
    assert second.success is False
    assert second.output["running"] is True

    log_path = wks_home / "logfile"
    log_text = log_path.read_text()
    assert "ERROR: Daemon already running" in log_text
    assert (wks_home / "daemon.lock").exists()

    stop_result = run_cmd(cmd_stop)
    assert stop_result.success is True
    assert stop_result.output["stopped"] is True
    assert not (wks_home / "daemon.lock").exists()


@pytest.mark.daemon
def test_cmd_start_blocking(monkeypatch):
    """Verify that blocking=True calls run_foreground."""
    from unittest.mock import MagicMock

    # Mock Daemon class to verify method calls
    mock_daemon_instance = MagicMock()
    mock_daemon_cls = MagicMock(return_value=mock_daemon_instance)

    monkeypatch.setattr("wks.api.daemon.cmd_start.Daemon", mock_daemon_cls)

    from wks.api.daemon.cmd_start import cmd_start

    # Simulate run_foreground returning (which it does on exception or stop)
    # Here we just want to ensure it's called.
    run_cmd(cmd_start, blocking=True)

    mock_daemon_instance.run_foreground.assert_called_once()
    mock_daemon_instance.start.assert_not_called()

    # Verify existing behavior (blocking=False)
    mock_daemon_instance.reset_mock()
    run_cmd(cmd_start, blocking=False)
    mock_daemon_instance.start.assert_called_once()
    mock_daemon_instance.run_foreground.assert_not_called()
