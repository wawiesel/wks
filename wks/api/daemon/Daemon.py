"""Daemon public API (TDD-focused, watchdog-based)."""

import threading
import time
from pathlib import Path
from typing import Any

from watchdog.observers import Observer

from ..config.WKSConfig import WKSConfig
from .DaemonConfig import DaemonConfig
from .FilesystemEvents import FilesystemEvents
from ._EventHandler import _EventHandler
from ._write_status_file import write_status_file
from ._extract_log_messages import extract_log_messages


class Daemon:
    """Minimal daemon runtime API for TDD."""

    _global_instance: "Daemon | None" = None
    _global_lock = threading.Lock()

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._handler: _EventHandler | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._config: DaemonConfig | None = None
        self._log_path: Path | None = None
        self._current_restrict: str = ""
        self._lock_path: Path | None = None

    def _load_config(self) -> DaemonConfig:
        config = WKSConfig.load()
        return config.daemon

    def _resolve_watch_paths(self, restrict_dir: Path | None) -> list[Path]:
        # Priority: explicit restrict_dir -> monitor include_paths
        paths: list[Path] = []
        if restrict_dir is not None:
            paths.append(restrict_dir.expanduser().resolve())
        else:
            monitor_paths = WKSConfig.load().monitor.filter.include_paths
            paths.extend(Path(p).expanduser().resolve() for p in monitor_paths)
        # Deduplicate
        unique: list[Path] = []
        seen = set()
        for p in paths:
            if p not in seen:
                unique.append(p)
                seen.add(p)
        return unique

    def start(self, restrict_dir: Path | None = None) -> Any:
        """Start the daemon watcher in a background thread."""
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                # Already running: operate on the running instance, log warning, return current state
                running = Daemon._global_instance
                running._append_log("WARN: Daemon already running")
                running._write_status(
                    running=True,
                    restrict_dir=Path(running._current_restrict) if running._current_restrict else None,
                )
                return type(
                    "DaemonStatus",
                    (),
                    {
                        "running": True,
                        "pid": None,
                        "log_path": str(running._log_path) if running._log_path else None,
                        "restrict_dir": running._current_restrict,
                    },
                )

        self._config = self._load_config()
        home = WKSConfig.get_home_dir()
        self._log_path = home / "logs" / "daemon.log"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = home / "daemon.lock"
        self._lock_path.write_text("running", encoding="utf-8")

        watch_paths = self._resolve_watch_paths(restrict_dir)
        self._handler = _EventHandler()
        self._observer = Observer()
        for path in watch_paths:
            if path.exists():
                self._observer.schedule(self._handler, str(path), recursive=True)

        self._observer.start()
        self._running = True
        self._stop_event.clear()
        self._current_restrict = str(restrict_dir) if restrict_dir else ""
        with self._global_lock:
            Daemon._global_instance = self

        self._append_log("INFO: Daemon started")

        def _loop() -> None:
            while not self._stop_event.is_set():
                time.sleep(self._config.sync_interval_secs)
                # Periodically write status
                self._write_status(running=True, restrict_dir=restrict_dir)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

        self._write_status(running=True, restrict_dir=restrict_dir)

        return type(
            "DaemonStatus",
            (),
            {
                "running": True,
                "pid": None,
                "log_path": str(self._log_path) if self._log_path else None,
                "restrict_dir": self._current_restrict,
            },
        )

    def stop(self) -> Any:
        """Stop the daemon watcher."""
        target = self
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                target = Daemon._global_instance
        target._stop_event.set()
        if target._observer:
            target._observer.stop()
            target._observer.join()
        if target._thread:
            target._thread.join(timeout=2)
        target._running = False
        target._write_status(running=False, restrict_dir=None)
        with self._global_lock:
            if Daemon._global_instance is target:
                Daemon._global_instance = None
        if target._lock_path and target._lock_path.exists():
            try:
                target._lock_path.unlink()
            except Exception:
                pass
        return type(
            "DaemonStatus",
            (),
            {
                "running": False,
                "pid": None,
                "log_path": str(target._log_path) if target._log_path else None,
                "restrict_dir": target._current_restrict,
            },
        )

    def status(self) -> Any:
        """Return current status."""
        target = self
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                target = Daemon._global_instance
        return type(
            "DaemonStatus",
            (),
            {
                "running": target._running,
                "pid": None,
                "log_path": str(target._log_path) if target._log_path else None,
                "restrict_dir": target._current_restrict,
            },
        )

    def get_filesystem_events(self) -> FilesystemEvents:
        """Return and clear accumulated events."""
        if not self._handler:
            return FilesystemEvents(modified=[], created=[], deleted=[], moved=[])
        return self._handler.get_and_clear_events()

    def clear_events(self) -> None:
        """Explicitly clear accumulated events."""
        if self._handler:
            self._handler.get_and_clear_events()

    def _write_status(self, *, running: bool, restrict_dir: Path | None) -> None:
        """Write daemon status to daemon.json."""
        home = WKSConfig.get_home_dir()
        restrict_value = str(restrict_dir) if restrict_dir else self._current_restrict
        self._current_restrict = restrict_value
        warnings_log, errors_log = extract_log_messages(self._log_path) if self._log_path else ([], [])
        status = {
            "errors": errors_log,
            "warnings": warnings_log,
            "running": running,
            "pid": None,
            "restrict_dir": restrict_value,
            "log_path": str(self._log_path) if self._log_path else "",
        }
        write_status_file(status, wks_home=home)

    def _append_log(self, message: str) -> None:
        """Append a line to the daemon log."""
        if not self._log_path:
            return
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{message}\n")
        except Exception:
            pass
