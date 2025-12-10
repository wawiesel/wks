"""Daemon public API (TDD-focused, watchdog-based)."""

import threading
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..config.WKSConfig import WKSConfig
from .DaemonConfig import DaemonConfig
from .FilesystemEvents import FilesystemEvents


class _EventHandler(FileSystemEventHandler):
    """Handles filesystem events and accumulates them."""

    def __init__(self) -> None:
        super().__init__()
        self._modified: set[str] = set()
        self._created: set[str] = set()
        self._deleted: set[str] = set()
        self._moved: dict[str, str] = {}
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._modified.add(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._created.add(event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._deleted.add(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._moved[event.src_path] = event.dest_path

    def get_and_clear_events(self) -> FilesystemEvents:
        with self._lock:
            modified = list(self._modified)
            created = list(self._created)
            deleted = list(self._deleted)
            moved = list(self._moved.items())
            self._modified.clear()
            self._created.clear()
            self._deleted.clear()
            self._moved.clear()
        return FilesystemEvents(modified=modified, created=created, deleted=deleted, moved=moved)


class Daemon:
    """Minimal daemon runtime API for TDD."""

    def __init__(self) -> None:
        self._observer: Observer | None = None
        self._handler: _EventHandler | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._config: DaemonConfig | None = None
        self._log_path: Path | None = None

    def _load_config(self) -> DaemonConfig:
        config = WKSConfig.load()
        return config.daemon

    def _resolve_watch_paths(self, restrict_dir: Path | None) -> list[Path]:
        # Priority: explicit restrict_dir -> config.daemon.restrict_dir -> monitor include_paths
        paths: list[Path] = []
        if restrict_dir is not None:
            paths.append(restrict_dir.expanduser().resolve())
        else:
            cfg = self._config or self._load_config()
            if cfg.restrict_dir != "":
                paths.append(Path(cfg.restrict_dir).expanduser().resolve())
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
        if self._running:
            raise RuntimeError("Daemon already running for this process")

        self._config = self._load_config()
        self._log_path = WKSConfig.get_home_dir() / self._config.log_file

        watch_paths = self._resolve_watch_paths(restrict_dir)
        self._handler = _EventHandler()
        self._observer = Observer()
        for path in watch_paths:
            if path.exists():
                self._observer.schedule(self._handler, str(path), recursive=True)

        self._observer.start()
        self._running = True
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.is_set():
                time.sleep(self._config.sync_interval_secs)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

        return type("DaemonStatus", (), {"running": True, "pid": None, "log_path": str(self._log_path) if self._log_path else None})

    def stop(self) -> Any:
        """Stop the daemon watcher."""
        self._stop_event.set()
        if self._observer:
            self._observer.stop()
            self._observer.join()
        if self._thread:
            self._thread.join(timeout=2)
        self._running = False
        return type("DaemonStatus", (), {"running": False, "pid": None, "log_path": str(self._log_path) if self._log_path else None})

    def status(self) -> Any:
        """Return current status."""
        return type("DaemonStatus", (), {"running": self._running, "pid": None, "log_path": str(self._log_path) if self._log_path else None})

    def get_filesystem_events(self) -> FilesystemEvents:
        """Return and clear accumulated events."""
        if not self._handler:
            return FilesystemEvents(modified=[], created=[], deleted=[], moved=[])
        return self._handler.get_and_clear_events()

    def clear_events(self) -> None:
        """Explicitly clear accumulated events."""
        if self._handler:
            self._handler.get_and_clear_events()
