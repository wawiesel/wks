import os
import signal
import sys
import time
from pathlib import Path

from watchdog.observers import Observer

from ..config.WKSConfig import WKSConfig
from ..config.write_status_file import write_status_file
from ..log.read_log_entries import read_log_entries
from ..monitor.explain_path import explain_path
from ._daemon_log_with_path import _daemon_log_with_path
from ._EventHandler import _EventHandler
from ._sync_path_static import _sync_path_static


def _child_main(
    home_dir: str,
    _log_path: str,
    paths: list[str],
    restrict_val: str,
    sync_interval: float,
    status_path: str,
    lock_path: str,
) -> None:
    # Load monitor config for filtering
    wks_config = None
    try:
        wks_config = WKSConfig.load()
        monitor_cfg = wks_config.monitor
        home_debug = str(WKSConfig.get_home_dir())
    except Exception as exc:
        # Fallback if config fails load in child
        # We must log this because it disables filtering!
        monitor_cfg = None
        home_debug = "UNKNOWN"
        # We can't use append_log yet because log_file isn't set up until below.
        # So we'll store the error and log it after setup.
        startup_error: str | None = f"ERROR: Failed to load monitor config in child: {exc}"
    else:
        startup_error = None

    # Detach child stdio to avoid blocking or noisy output
    try:
        devnull = Path(os.devnull).open("w")  # noqa: SIM115
        sys.stdout = devnull  # type: ignore
        sys.stderr = devnull  # type: ignore
    except Exception:
        pass

    status_file = Path(status_path)
    lock_file = Path(lock_path)

    # Define log_file for status reporting and ignore paths
    log_file = Path(_log_path)

    def append_log(message: str) -> None:
        # Parse level from message prefix (e.g., "INFO: ..." or "ERROR: ...")
        if message.startswith("DEBUG:"):
            _daemon_log_with_path(log_file, "DEBUG", message[6:].strip())
        elif message.startswith("INFO:"):
            _daemon_log_with_path(log_file, "INFO", message[5:].strip())
        elif message.startswith("WARN:"):
            _daemon_log_with_path(log_file, "WARN", message[5:].strip())
        elif message.startswith("ERROR:") or message.startswith("FATAL:"):
            _daemon_log_with_path(log_file, "ERROR", message[6:].strip())
        else:
            _daemon_log_with_path(log_file, "INFO", message)

    stop_flag = False

    if startup_error:
        append_log(startup_error)
    else:
        append_log(f"DEBUG: Daemon WKS_HOME={home_debug} (config loaded)")

    # Pre-flight check: Ensure database is accessible/startable
    # This prevents the daemon from entering a crash loop if mongod is missing.
    if not startup_error:
        try:
            from ..database.Database import Database

            # Attempt a quick connection/start
            # We use a zero-timeout or very short timeout check if possible,
            # but Database init with local=True triggers _ensure_local_mongod which checks binary
            assert monitor_cfg is not None
            assert wks_config is not None
            database_name = f"{wks_config.database.prefix}.monitor"
            with Database(wks_config.database, database_name) as db:
                db.get_client().server_info()
        except Exception as exc:
            append_log(f"FATAL: Database initialization failed: {exc}")
            # Write error status and exit
            status = {
                "errors": [f"Database initialization failed: {exc}"],
                "warnings": [],
                "running": False,
                "pid": None,
                "restrict_dir": restrict_val,
                "log_path": str(log_file),
                "lock_path": lock_path,
                "last_sync": None,
            }
            write_status_file(status, wks_home=Path(home_dir), filename="daemon.json")
            return

    def handle_sigterm(_signum, _frame):
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

    # Get logfile path for ignore_paths
    log_file = Path(_log_path)

    def write_status(running: bool) -> None:
        if wks_config:
            log_cfg = wks_config.log
            d_ret = log_cfg.debug_retention_days
            i_ret = log_cfg.info_retention_days
            w_ret = log_cfg.warning_retention_days
            e_ret = log_cfg.error_retention_days
        else:
            # Defaults if config failed to load
            d_ret = 0.5
            i_ret = 1.0
            w_ret = 2.0
            e_ret = 7.0

        warnings_log, errors_log = read_log_entries(
            log_file,
            debug_retention_days=d_ret,
            info_retention_days=i_ret,
            warning_retention_days=w_ret,
            error_retention_days=e_ret,
        )
        import datetime

        status = {
            "errors": errors_log,
            "warnings": warnings_log,
            "running": running,
            "pid": os.getpid() if running else None,
            "restrict_dir": restrict_val,
            "log_path": str(log_file),
            "lock_path": lock_path,
            "last_sync": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        write_status_file(status, wks_home=Path(home_dir), filename="daemon.json")

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
            if monitor_cfg is None:
                to_sync.add(p_path)
            else:
                allowed, _reason = explain_path(monitor_cfg, p_path)
                if allowed:
                    to_sync.add(p_path)

        for src_path, dest_path in filtered_moved:
            if src_path not in ignore_paths and (monitor_cfg is None or explain_path(monitor_cfg, src_path)[0]):
                to_delete.add(src_path)
            if dest_path not in ignore_paths and (monitor_cfg is None or explain_path(monitor_cfg, dest_path)[0]):
                to_sync.add(dest_path)

        for p_path in filtered_deleted:
            if monitor_cfg is None or explain_path(monitor_cfg, p_path)[0]:
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
