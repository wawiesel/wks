"""Daemon status command (reads daemon.json)."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.write_status_file import write_status_file
from ..log.read_log_entries import read_log_entries
from . import DaemonStatusOutput


def cmd_status() -> StageResult:
    """Return daemon status by reading daemon.json."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Checking daemon status...")
        try:
            home = WKSConfig.get_home_dir()
            log_path = WKSConfig.get_logfile_path()
            lock_path = home / "daemon.lock"
            status_path = home / "daemon.json"

            # 1. Determine Liveness (True Source of Truth)
            is_running = False
            actual_pid = None
            if lock_path.exists():
                try:
                    import os

                    pid_val = int(lock_path.read_text().strip())
                    os.kill(pid_val, 0)
                    is_running = True
                    actual_pid = pid_val
                except (ValueError, OSError):
                    pass

            # 2. Derive Status
            if is_running:
                # If running, the daemon's output file IS the record.
                # We read it directly.
                import json

                try:
                    status_data = json.loads(status_path.read_text())
                    # Ensure metadata is consistent with our view if needed, or just trust it.
                    # We trust it, but we might want to ensure log_path is current config's path?
                    # No, daemon uses config's path.
                except (FileNotFoundError, json.JSONDecodeError):
                    # Running but file missing/corrupt? Fallback to synthesizing partial status
                    log_cfg = WKSConfig.load().log
                    warnings, errors = read_log_entries(
                        log_path,
                        debug_retention_days=log_cfg.debug_retention_days,
                        info_retention_days=log_cfg.info_retention_days,
                        warning_retention_days=log_cfg.warning_retention_days,
                        error_retention_days=log_cfg.error_retention_days,
                    )
                    status_data = {
                        "errors": errors,
                        "warnings": warnings,
                        "running": True,
                        "pid": actual_pid,
                        "restrict_dir": "UNKNOWN",  # Can't know without file
                        "log_path": str(log_path),
                        "lock_path": str(lock_path),
                        "last_sync": None,
                    }
                    # We might want to fix the file?
                    write_status_file(status_data, wks_home=home, filename="daemon.json")
            else:
                # Stopped. Generate fresh status.
                log_cfg = WKSConfig.load().log
                warnings, errors = read_log_entries(
                    log_path,
                    debug_retention_days=log_cfg.debug_retention_days,
                    info_retention_days=log_cfg.info_retention_days,
                    warning_retention_days=log_cfg.warning_retention_days,
                    error_retention_days=log_cfg.error_retention_days,
                )

                status_data = {
                    "errors": errors,
                    "warnings": warnings,
                    "running": False,
                    "pid": None,
                    "restrict_dir": "",
                    "log_path": str(log_path),
                    "lock_path": str(lock_path),
                    "last_sync": None,
                    # Stopped, we don't know last sync unless we parse old file, but user said "don't read stats".
                }
                # Update the file to reflect "Stopped"
                write_status_file(status_data, wks_home=home, filename="daemon.json")

            result_obj.result = "Daemon status retrieved"
            result_obj.output = DaemonStatusOutput(**status_data).model_dump(mode="python")
            result_obj.success = True
            yield (1.0, "Complete")
        except Exception as exc:
            home = WKSConfig.get_home_dir()
            log_path = WKSConfig.get_logfile_path()
            result_obj.result = f"Error checking daemon status: {exc}"
            result_obj.output = DaemonStatusOutput(
                errors=[str(exc)],
                warnings=[],
                running=False,
                pid=None,
                restrict_dir="",
                log_path=str(log_path),
                lock_path=str(home / "daemon.lock"),
                last_sync=None,
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
