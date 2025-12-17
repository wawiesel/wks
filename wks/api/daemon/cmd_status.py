"""Daemon status command (reads daemon.json)."""

from collections.abc import Iterator
from pathlib import Path

from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import DaemonStatusOutput
from ._read_status_file import read_status_file


def cmd_status() -> StageResult:
    """Return daemon status by reading daemon.json."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Checking daemon status...")
        try:
            home = WKSConfig.get_home_dir()
            # Read status file for metadata (logs/restrict_dir), but ignore its 'running' state
            raw = read_status_file(home)

            # 1. Recover persistent config from stale status file
            restrict_dir = raw.get("restrict_dir", "")
            log_path_str = raw.get("log_path", str(home / "logs" / "daemon.log"))
            old_last_sync: str | None = raw.get("last_sync")

            # 2. Check lock file for authoritative PID and running state
            lock_path = home / "daemon.lock"
            actual_pid = None
            is_running = False

            if lock_path.exists():
                try:
                    import os

                    pid_val = int(lock_path.read_text().strip())
                    actual_pid = pid_val  # Set PID regardless of liveness (user request)
                    os.kill(pid_val, 0)
                    is_running = True
                except (ValueError, OSError):
                    pass

            # 3. Freshly parse logs for errors/warnings
            from ._extract_log_messages import extract_log_messages

            warnings, errors = extract_log_messages(Path(log_path_str))

            # 4. Construct fresh status and override daemon.json
            from ._write_status_file import write_status_file

            # If stopped, we MUST preserve the old timestamp to show when it LAST ran.
            last_sync_val: str | None
            if is_running:
                import datetime

                last_sync_val = datetime.datetime.now(datetime.timezone.utc).isoformat()
            else:
                last_sync_val = old_last_sync

            new_status = {
                "errors": errors,
                "warnings": warnings,
                "running": is_running,
                "pid": actual_pid,
                "restrict_dir": restrict_dir,
                "log_path": log_path_str,
                "lock_path": str(lock_path),
                "last_sync": last_sync_val,
            }

            write_status_file(new_status, wks_home=home)

            result_obj.result = "Daemon status retrieved"
            result_obj.output = DaemonStatusOutput(
                errors=errors,
                warnings=warnings,
                running=is_running,
                pid=actual_pid,
                restrict_dir=restrict_dir,
                log_path=log_path_str,
                lock_path=str(lock_path),
                last_sync=last_sync_val,
            ).model_dump(mode="python")
            result_obj.success = True
            yield (1.0, "Complete")
        except Exception as exc:
            home = WKSConfig.get_home_dir()
            log_path = str(home / "logs" / "daemon.log")
            result_obj.result = f"Error checking daemon status: {exc}"
            result_obj.output = DaemonStatusOutput(
                errors=[str(exc)],
                warnings=[],
                running=False,
                pid=None,
                restrict_dir="",
                log_path=log_path,
                lock_path=str(home / "daemon.lock"),
                last_sync=None,
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
