"""Daemon clear command (resets state)."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import DaemonClearOutput
from ._read_status_file import read_status_file
from ._write_status_file import write_status_file


def cmd_clear() -> StageResult:
    """Clear daemon logs and status if not running."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Checking daemon status...")
        home = WKSConfig.get_home_dir()

        # Read status for metadata (log location)
        status = read_status_file(home)

        # Check lock file for authoritative running state
        lock_path = home / "daemon.lock"
        if lock_path.exists():
            try:
                import os

                pid = int(lock_path.read_text().strip())
                os.kill(pid, 0)
                # If we get here, process is alive
                result_obj.success = False
                result_obj.result = "Cannot clear while daemon is running"
                result_obj.output = DaemonClearOutput(
                    errors=["Cannot clear while daemon is running"],
                    warnings=[],
                    cleared=False,
                    message="Daemon is running",
                ).model_dump(mode="python")
                yield (1.0, "Complete")
                return
            except (ValueError, OSError):
                # Lock exists but invalid or process dead -> stale
                pass

        yield (0.3, "Clearing logs...")
        log_path_str = status.get("log_path") or str(home / "logs" / "daemon.log")
        if log_path_str:
            log_path = Path(log_path_str)
            if log_path.exists():
                try:
                    # Truncate file
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
                # Log but continue, as it might be a permission issue or race
                # But since we checked status.running is False, it should be fine.
                warnings = [f"Failed to remove lock file: {e}"]
                result_obj.output = DaemonClearOutput(
                    errors=[],
                    warnings=warnings,
                    cleared=False,  # Partially failed? Or just minimal success?
                    # Let's consider it a non-critical failure for "cleared" if we fixed status,
                    # but if lock implies running, maybe we shouldn't have proceeded.
                    # But status said not running. So lock is stale.
                    message="Cleared logs but failed to remove lock file",
                ).model_dump(mode="python")
                # We can continue to reset status file though.

        yield (0.6, "Resetting status file...")
        # Reset to clean stopped state
        clean_status: dict[str, Any] = {
            "running": False,
            "pid": None,
            "restrict_dir": "",
            "log_path": log_path_str or str(home / "logs" / "daemon.log"),
            "lock_path": str(home / "daemon.lock"),
            "last_sync": None,
            "errors": [],
            "warnings": [],
        }
        write_status_file(clean_status, wks_home=home)

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
