"""Daemon filesystem event integration test (real backend, restricted dir)."""

import platform
import time
from pathlib import Path

import pytest
from watchdog.observers import Observer

from wks.api.service.Service import Service
from tests.unit.conftest import minimal_wks_config


@pytest.mark.daemon
def test_daemon_reports_fs_events(monkeypatch, tmp_path):
    if platform.system().lower() != "darwin":
        pytest.skip("Daemon filesystem test runs on darwin backend")

    cfg = minimal_wks_config()
    cfg.daemon.sync_interval_secs = 0.05

    # Set WKS_HOME
    wks_home = tmp_path / ".wks"
    wks_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WKS_HOME", str(wks_home))
    cfg.save()

    # Restrict to a temp directory
    rdir = tmp_path / "xtest"
    rdir.mkdir(parents=True, exist_ok=True)

    # Use public Daemon; access impl internals only through the instance
    with Service(cfg.service) as d:
        impl = d._impl  # type: ignore[attr-defined]

        # Manually wire observer/handler (mirrors run setup) without importing _Impl
        handler_cls = type(impl)._DaemonEventHandler  # type: ignore[attr-defined]
        handler = handler_cls()
        observer = Observer()
        observer.schedule(handler, str(rdir), recursive=True)
        observer.start()

        try:
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

            events = handler.get_and_clear_events()
        finally:
            observer.stop()
            observer.join()

    # Validate event contents
    assert events is not None
    # Creation of f1
    assert str(f1) in events.created
    # Modification may or may not be captured distinctly; allow empty modified
    # Deletion of f1
    assert str(f1) in events.deleted
    # Move of f2 -> f2_renamed
    assert (str(f2), str(f2_renamed)) in [(old, new) for old, new in events.moved]
    # All paths within restricted dir
    all_paths = (
        events.modified
        + events.created
        + events.deleted
        + [p for old, new in events.moved for p in (old, new)]
    )
    assert all(str(p).startswith(str(rdir)) for p in all_paths)
