"""Daemon public API (TDD-focused, watchdog-based)."""

import json
import os
import signal
import subprocess
import sys
import time
import threading
from pathlib import Path
from typing import Any

from watchdog.observers import Observer

from .DaemonConfig import DaemonConfig
from .FilesystemEvents import FilesystemEvents
from ._EventHandler import _EventHandler
from ._write_status_file import write_status_file
from ._extract_log_messages import extract_log_messages


def _append_log_file(log_file: Path, message: str) -> None:
    """Append a line to a log file (process-safe)."""
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{message}\n")
    except Exception:
        pass


def _sync_path_static(path: Path, log_file: Path, log_fn) -> None:
    """Invoke monitor sync for a single path (child process safe)."""
    try:
        from ..monitor.cmd_sync import cmd_sync

        result = cmd_sync(str(path))
        list(result.progress_callback(result))
        out = result.output or {}
        errs = out.get("errors", [])
        warns = out.get("warnings", [])
        for msg in warns:
            log_fn(f"WARN: {msg}")
        for msg in errs:
            log_fn(f"ERROR: {msg}")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_fn(f"ERROR: sync failed for {path}: {exc}")


def _child_main(
    home_dir: str,
    log_path: str,
    paths: list[str],
    restrict_val: str,
    sync_interval: float,
    status_path: str,
    lock_path: str,
) -> None:
    # Detach child stdio to avoid blocking or noisy output
    try:
        devnull = open(os.devnull, "w")
        sys.stdout = devnull  # type: ignore
        sys.stderr = devnull  # type: ignore
    except Exception:
        pass

    log_file = Path(log_path)
    status_file = Path(status_path)
    lock_file = Path(lock_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def append_log(message: str) -> None:
        _append_log_file(log_file, message)

    stop_flag = False

    def handle_sigterm(signum, frame):
        nonlocal stop_flag
        stop_flag = True
        append_log("INFO: Received SIGTERM")

    signal.signal(signal.SIGTERM, handle_sigterm)

    observer = Observer()
    handler = _EventHandler()
    for p in paths:
        path_obj = Path(p)
        if path_obj.exists():
            observer.schedule(handler, str(path_obj), recursive=True)
            append_log(f"INFO: Watching {path_obj}")
        else:
            append_log(f"WARN: Watch path missing {path_obj}")

    observer.start()
    append_log("INFO: Daemon child started")

    def write_status(running: bool) -> None:
        warnings_log, errors_log = extract_log_messages(log_file) if log_file else ([], [])
        status = {
            "errors": errors_log,
            "warnings": warnings_log,
            "running": running,
            "pid": os.getpid(),
            "restrict_dir": restrict_val,
            "log_path": str(log_file),
        }
        write_status_file(status, wks_home=Path(home_dir))

    def process_events() -> None:
        events = handler.get_and_clear_events()
        ignore_paths = {log_file.resolve(), status_file.resolve(), lock_file.resolve()}

        filtered_modified = [Path(p).resolve() for p in events.modified if Path(p).resolve() not in ignore_paths]
        filtered_created = [Path(p).resolve() for p in events.created if Path(p).resolve() not in ignore_paths]
        filtered_deleted = [Path(p).resolve() for p in events.deleted if Path(p).resolve() not in ignore_paths]
        filtered_moved = [
            (Path(src).resolve(), Path(dest).resolve())
            for src, dest in events.moved
            if Path(src).resolve() not in ignore_paths or Path(dest).resolve() not in ignore_paths
        ]

        if not (filtered_modified or filtered_created or filtered_deleted or filtered_moved):
            return

        append_log(
            f"INFO: events modified={len(filtered_modified)} "
            f"created={len(filtered_created)} deleted={len(filtered_deleted)} moved={len(filtered_moved)}"
        )
        to_delete: set[Path] = set()
        to_sync: set[Path] = set()
        for p_path in filtered_modified + filtered_created:
            to_sync.add(p_path)
        for src_path, dest_path in filtered_moved:
            if src_path not in ignore_paths:
                to_delete.add(src_path)
            if dest_path not in ignore_paths:
                to_sync.add(dest_path)
        for p_path in filtered_deleted:
            to_delete.add(p_path)
        for path in to_delete:
            _sync_path_static(path, log_file, append_log)
        for path in to_sync:
            _sync_path_static(path, log_file, append_log)

    write_status(running=True)
    iteration = 0
    try:
        while not stop_flag:
            iteration += 1
            process_events()
            write_status(running=True)
            time.sleep(sync_interval)
    finally:
        try:
            observer.stop()
            observer.join()
        except Exception:
            pass
        write_status(running=False)
        append_log("INFO: Daemon child exiting")


class Daemon:
    """Minimal daemon runtime API for TDD."""

    _global_instance: "Daemon | None" = None
    _global_lock = threading.Lock()

    def __init__(self) -> None:
        self._running = False
        self._config: DaemonConfig | None = None
        self._log_path: Path | None = None
        self._current_restrict: str = ""
        self._lock_path: Path | None = None
        self._pid: int | None = None

    def _load_config(self) -> DaemonConfig:
        from ..config.WKSConfig import WKSConfig

        config = WKSConfig.load()
        return config.daemon

    def _resolve_watch_paths(self, restrict_dir: Path | None) -> list[Path]:
        # Priority: explicit restrict_dir -> monitor include_paths
        from ..config.WKSConfig import WKSConfig

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

    def _pid_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running."""
        try:
            os.kill(pid, 0)  # Signal 0 checks existence without killing
            return True
        except OSError:
            return False

    def start(self, restrict_dir: Path | None = None) -> Any:
        """Start the daemon watcher in a background thread."""
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                running = Daemon._global_instance
                running._append_log("ERROR: Daemon already running")
                raise RuntimeError("Daemon already running")

        self._config = self._load_config()
        from ..config.WKSConfig import WKSConfig

        home = WKSConfig.get_home_dir()
        self._log_path = home / "logs" / "daemon.log"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = home / "daemon.lock"
        existing_pid = None
        if self._lock_path.exists():
            try:
                existing_pid = int(self._lock_path.read_text().strip())
                if existing_pid > 0 and self._pid_running(existing_pid):
                    self._append_log("ERROR: Daemon already running")
                    raise RuntimeError("Daemon already running")
            except Exception:
                existing_pid = None

        watch_paths = self._resolve_watch_paths(restrict_dir)
        restrict_value = str(restrict_dir) if restrict_dir else ""

        self._current_restrict = restrict_value
        status_path = home / "daemon.json"

        # Use subprocess.Popen for true process independence
        paths_json = json.dumps([str(p) for p in watch_paths])
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "wks.api.daemon._child_runner",
                str(home),
                str(self._log_path),
                paths_json,
                restrict_value,
                str(self._config.sync_interval_secs),
                str(status_path),
                str(self._lock_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process group
        )
        self._pid = proc.pid
        self._lock_path.write_text(str(self._pid), encoding="utf-8")

        self._running = True
        self._append_log("INFO: Daemon started (parent)")

        self._write_status(running=True, restrict_dir=restrict_dir)

        return type(
            "DaemonStatus",
            (),
            {
                "running": True,
                "pid": self._pid,
                "log_path": str(self._log_path) if self._log_path else None,
                "restrict_dir": self._current_restrict,
            },
        )

    def stop(self) -> Any:
        """Stop the daemon watcher."""
        from ..config.WKSConfig import WKSConfig

        home = WKSConfig.get_home_dir()
        lock_path = home / "daemon.lock"
        self._lock_path = lock_path
        self._log_path = home / "logs" / "daemon.log"

        pid_to_stop = None
        if lock_path.exists():
            try:
                pid_to_stop = int(lock_path.read_text().strip())
            except Exception:
                pid_to_stop = None
        if pid_to_stop:
            try:
                os.kill(pid_to_stop, signal.SIGTERM)
            except Exception:
                pass  # Process may have already exited
        self._running = False
        self._write_status(running=False, restrict_dir=None)
        if lock_path.exists():
            try:
                lock_path.unlink()
            except Exception:
                pass
        return type(
            "DaemonStatus",
            (),
            {
                "running": False,
                "pid": pid_to_stop,
                "log_path": str(self._log_path) if self._log_path else None,
                "restrict_dir": self._current_restrict,
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
                "pid": target._pid,
                "log_path": str(target._log_path) if target._log_path else None,
                "restrict_dir": target._current_restrict,
            },
        )

    def get_filesystem_events(self) -> FilesystemEvents:
        """Return and clear accumulated events.

        Note: Since the daemon runs in a subprocess, events are synced
        directly to the monitor database. This method returns empty.
        """
        return FilesystemEvents(modified=[], created=[], deleted=[], moved=[])

    def clear_events(self) -> None:
        """Explicitly clear accumulated events.

        Note: Since the daemon runs in a subprocess, this is a no-op.
        """
        pass

    def _write_status(self, *, running: bool, restrict_dir: Path | None) -> None:
        """Write daemon status to daemon.json."""
        from ..config.WKSConfig import WKSConfig

        home = WKSConfig.get_home_dir()
        restrict_value = str(restrict_dir) if restrict_dir else self._current_restrict
        self._current_restrict = restrict_value
        warnings_log, errors_log = extract_log_messages(self._log_path) if self._log_path else ([], [])
        log_path = str(self._log_path) if self._log_path else str(home / "logs" / "daemon.log")
        status = {
            "errors": errors_log,
            "warnings": warnings_log,
            "running": running,
            "pid": self._pid,
            "restrict_dir": restrict_value,
            "log_path": log_path,
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
