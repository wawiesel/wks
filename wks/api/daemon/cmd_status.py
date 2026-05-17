from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.write_status_file import write_status_file
from ..log.read_log_entries import read_log_entries
from ..log.summarize_status_log_messages import summarize_status_log_messages
from . import DaemonStatusOutput
from .process_identity import active_wks_daemon_lock


def cmd_status() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Checking daemon status...")
        try:
            home = WKSConfig.get_home_dir()
            log_path = WKSConfig.get_logfile_path()
            lock_path = home / "daemon.lock"
            status_path = home / "daemon.json"

            is_running = False
            actual_pid = active_wks_daemon_lock(lock_path, status_path=status_path)
            if actual_pid is not None:
                is_running = True

            if is_running:
                import json

                try:
                    status_data = json.loads(status_path.read_text())
                    status_data["warnings"], status_data["errors"] = summarize_status_log_messages(
                        status_data.get("warnings", []),
                        status_data.get("errors", []),
                    )
                except (FileNotFoundError, json.JSONDecodeError):
                    log_cfg = WKSConfig.load().log
                    warnings, errors = read_log_entries(
                        log_path,
                        debug_retention_days=log_cfg.debug_retention_days,
                        info_retention_days=log_cfg.info_retention_days,
                        warning_retention_days=log_cfg.warning_retention_days,
                        error_retention_days=log_cfg.error_retention_days,
                    )
                    warnings, errors = summarize_status_log_messages(warnings, errors)
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
                    write_status_file(status_data, wks_home=home, filename="daemon.json")
            else:
                log_cfg = WKSConfig.load().log
                warnings, errors = read_log_entries(
                    log_path,
                    debug_retention_days=log_cfg.debug_retention_days,
                    info_retention_days=log_cfg.info_retention_days,
                    warning_retention_days=log_cfg.warning_retention_days,
                    error_retention_days=log_cfg.error_retention_days,
                )
                warnings, errors = summarize_status_log_messages(warnings, errors)

                status_data = {
                    "errors": errors,
                    "warnings": warnings,
                    "running": False,
                    "pid": None,
                    "restrict_dir": "",
                    "log_path": str(log_path),
                    "lock_path": str(lock_path),
                    "last_sync": None,
                }
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
