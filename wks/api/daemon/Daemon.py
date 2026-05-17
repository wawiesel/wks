import json
import os
import signal
import subprocess
import sys
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from ..config.WKSConfig import WKSConfig
from ..config.write_status_file import write_status_file
from ..log.append_log import append_log
from ..log.read_log_entries import read_log_entries
from ..log.summarize_status_log_messages import summarize_status_log_messages
from ._child_main import _child_main
from .DaemonConfig import DaemonConfig
from .FilesystemEvents import FilesystemEvents
from .process_identity import active_wks_daemon_lock


class Daemon:
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
        config = WKSConfig.load()
        return config.daemon

    def _resolve_watch_paths(self, restrict_dir: Path | None) -> list[Path]:
        from wks.api.config.normalize_path import normalize_path

        paths: list[Path] = []
        if restrict_dir is not None:
            paths.append(normalize_path(restrict_dir))
        else:
            monitor_paths = WKSConfig.load().monitor.filter.include_paths
            paths.extend(normalize_path(p) for p in monitor_paths)
        unique: list[Path] = []
        seen = set()
        for p in paths:
            if p not in seen:
                unique.append(p)
                seen.add(p)
        return unique

    def start(self, restrict_dir: Path | None = None) -> Any:
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                running = Daemon._global_instance
                running._append_log("ERROR: Daemon already running")
                raise RuntimeError("Daemon already running")

        self._config = self._load_config()

        home = WKSConfig.get_home_dir()
        self._log_path = WKSConfig.get_logfile_path()
        self._lock_path = home / "daemon.lock"
        status_path = home / "daemon.json"
        existing_pid = active_wks_daemon_lock(
            self._lock_path,
            status_path=status_path,
            max_status_age_seconds=max(300.0, self._config.sync_interval_secs * 3.0),
        )
        if existing_pid is not None:
            self._append_log("ERROR: Daemon already running")
            raise RuntimeError("Daemon already running")
        if self._lock_path.exists():
            with suppress(Exception):
                self._lock_path.unlink()

        watch_paths = self._resolve_watch_paths(restrict_dir)
        restrict_value = str(restrict_dir) if restrict_dir else ""
        self._current_restrict = restrict_value
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

    def run_foreground(self, restrict_dir: Path | None = None) -> None:
        with self._global_lock:
            if Daemon._global_instance and Daemon._global_instance._running:
                raise RuntimeError("Daemon already running")

        self._config = self._load_config()

        home = WKSConfig.get_home_dir()
        self._log_path = WKSConfig.get_logfile_path()
        self._lock_path = home / "daemon.lock"
        status_path = home / "daemon.json"
        existing_pid = active_wks_daemon_lock(
            self._lock_path,
            status_path=status_path,
            max_status_age_seconds=max(300.0, self._config.sync_interval_secs * 3.0),
        )
        if existing_pid is not None:
            raise RuntimeError("Daemon already running")
        if self._lock_path.exists():
            with suppress(Exception):
                self._lock_path.unlink()

        watch_paths = self._resolve_watch_paths(restrict_dir)
        restrict_value = str(restrict_dir) if restrict_dir else ""
        self._current_restrict = restrict_value
        self._pid = os.getpid()
        self._lock_path.write_text(str(self._pid), encoding="utf-8")
        self._running = True

        try:
            _child_main(
                home_dir=str(home),
                _log_path=str(self._log_path),
                paths=[str(p) for p in watch_paths],
                restrict_val=restrict_value,
                sync_interval=self._config.sync_interval_secs,
                status_path=str(status_path),
                lock_path=str(self._lock_path),
            )
        finally:
            self._running = False
            if self._lock_path.exists():
                with suppress(Exception):
                    self._lock_path.unlink()

    def stop(self) -> Any:
        home = WKSConfig.get_home_dir()
        lock_path = home / "daemon.lock"
        self._lock_path = lock_path
        self._log_path = WKSConfig.get_logfile_path()

        pid_to_stop = None
        if lock_path.exists():
            with suppress(Exception):
                pid_to_stop = int(lock_path.read_text().strip())
        if pid_to_stop:
            with suppress(Exception):
                os.kill(pid_to_stop, signal.SIGTERM)
        self._running = False
        self._write_status(running=False, restrict_dir=None)
        if lock_path.exists():
            with suppress(Exception):
                lock_path.unlink()
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
        return FilesystemEvents(modified=[], created=[], deleted=[], moved=[])

    def clear_events(self) -> None:
        pass

    def _write_status(self, *, running: bool, restrict_dir: Path | None) -> None:
        home = WKSConfig.get_home_dir()
        restrict_value = str(restrict_dir) if restrict_dir else self._current_restrict
        self._current_restrict = restrict_value
        log_cfg = WKSConfig.load().log
        log_path = WKSConfig.get_logfile_path()
        warnings_log, errors_log = read_log_entries(
            log_path,
            debug_retention_days=log_cfg.debug_retention_days,
            info_retention_days=log_cfg.info_retention_days,
            warning_retention_days=log_cfg.warning_retention_days,
            error_retention_days=log_cfg.error_retention_days,
        )
        warnings_log, errors_log = summarize_status_log_messages(warnings_log, errors_log)
        import datetime

        status = {
            "errors": errors_log,
            "warnings": warnings_log,
            "running": running,
            "pid": self._pid if running else None,
            "restrict_dir": restrict_value,
            "log_path": str(log_path),
            "lock_path": str(self._lock_path) if self._lock_path else str(home / "daemon.lock"),
            "last_sync": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_status_file(status, wks_home=home, filename="daemon.json")

    def _append_log(self, message: str) -> None:
        log_path = WKSConfig.get_logfile_path()
        if message.startswith("ERROR:"):
            append_log(log_path, "daemon", "ERROR", message[6:].strip())
        elif message.startswith("INFO:"):
            append_log(log_path, "daemon", "INFO", message[5:].strip())
        elif message.startswith("WARN:"):
            append_log(log_path, "daemon", "WARN", message[5:].strip())
        else:
            append_log(log_path, "daemon", "INFO", message)
