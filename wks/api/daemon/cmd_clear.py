from collections.abc import Iterator
from typing import Any

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.write_status_file import write_status_file
from ..log.LOG_PATTERN import LOG_PATTERN
from . import DaemonClearOutput


def cmd_clear(errors_only: bool = False) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Checking daemon status...")
        home = WKSConfig.get_home_dir()

        if errors_only:
            yield (0.3, "Removing error entries from logfile...")
            log_path = WKSConfig.get_logfile_path()
            removed = 0
            if log_path.exists():
                try:
                    lines = log_path.read_text(errors="ignore").splitlines()
                    kept = []
                    for line in lines:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        match = LOG_PATTERN.match(stripped)
                        if match and match.group(3).upper() == "ERROR":
                            removed += 1
                            continue
                        kept.append(stripped)
                    log_path.write_text("\n".join(kept) + "\n" if kept else "", encoding="utf-8")
                except Exception as e:
                    result_obj.success = False
                    result_obj.result = f"Failed to clear errors: {e}"
                    result_obj.output = DaemonClearOutput(
                        errors=[str(e)], warnings=[], cleared=False, message="Error clear failed"
                    ).model_dump(mode="python")
                    yield (1.0, "Complete")
                    return

            result_obj.success = True
            result_obj.result = f"Cleared {removed} error entries from logfile"
            result_obj.output = DaemonClearOutput(
                errors=[], warnings=[], cleared=True, message=f"Removed {removed} error entries"
            ).model_dump(mode="python")
            yield (1.0, "Complete")
            return

        lock_path = home / "daemon.lock"
        if lock_path.exists():
            try:
                import os

                pid = int(lock_path.read_text().strip())
                os.kill(pid, 0)
                result_obj.success = False
                result_obj.result = "Cannot clear while daemon is running (use --errors-only to clear errors)"
                result_obj.output = DaemonClearOutput(
                    errors=["Cannot clear while daemon is running (use --errors-only to clear errors)"],
                    warnings=[],
                    cleared=False,
                    message="Daemon is running",
                ).model_dump(mode="python")
                yield (1.0, "Complete")
                return
            except (ValueError, OSError):
                pass

        yield (0.3, "Clearing logs...")
        log_path = WKSConfig.get_logfile_path()
        if log_path.exists():
            try:
                log_path.write_text("", encoding="utf-8")
            except Exception as e:
                result_obj.success = False
                result_obj.result = f"Failed to clear log file: {e}"
                result_obj.output = DaemonClearOutput(
                    errors=[str(e)], warnings=[], cleared=False, message="Log clear failed"
                ).model_dump(mode="python")
                yield (1.0, "Complete")
                return

        yield (0.5, "Removing lock file...")
        lock_path = home / "daemon.lock"
        if lock_path.exists():
            try:
                lock_path.unlink()
            except Exception as e:
                warnings = [f"Failed to remove lock file: {e}"]
                result_obj.output = DaemonClearOutput(
                    errors=[],
                    warnings=warnings,
                    cleared=False,  # Partially failed? Or just minimal success?
                    message="Cleared logs but failed to remove lock file",
                ).model_dump(mode="python")

        yield (0.6, "Resetting status file...")
        clean_status: dict[str, Any] = {
            "running": False,
            "pid": None,
            "restrict_dir": "",
            "log_path": str(log_path),
            "lock_path": str(home / "daemon.lock"),
            "last_sync": None,
            "errors": [],
            "warnings": [],
        }
        write_status_file(clean_status, wks_home=home, filename="daemon.json")

        result_obj.success = True
        result_obj.result = "Daemon state cleared"
        result_obj.output = DaemonClearOutput(
            errors=[], warnings=[], cleared=True, message="Daemon logs and status cleared"
        ).model_dump(mode="python")
        yield (1.0, "Complete")

    return StageResult(
        announce="Clearing daemon state...",
        progress_callback=do_work,
    )
