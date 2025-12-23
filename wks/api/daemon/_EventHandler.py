"""Filesystem event handler for daemon."""

import threading

from watchdog.events import FileSystemEvent, FileSystemEventHandler

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
                self._modified.add(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._created.add(str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._deleted.add(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:  # pragma: no cover
        if not event.is_directory:
            with self._lock:
                self._moved[str(event.src_path)] = str(event.dest_path)

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
