"""Daemon status command (reads daemon.json)."""

from collections.abc import Iterator

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
            raw = read_status_file(home)
            # Validate presence of required fields before schema dump
            running = raw["running"]
            pid = raw["pid"] if running else None
            restrict_dir = raw["restrict_dir"]
            log_path = raw["log_path"]

            result_obj.result = "Daemon status retrieved"
            result_obj.output = DaemonStatusOutput(
                errors=raw.get("errors", []),
                warnings=raw.get("warnings", []),
                running=running,
                pid=pid,
                restrict_dir=restrict_dir,
                log_path=log_path,
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
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
