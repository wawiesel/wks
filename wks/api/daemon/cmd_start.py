"""Start daemon (background watcher)."""

from pathlib import Path
from typing import Iterator

from ..StageResult import StageResult
from . import DaemonStartOutput, Daemon


def cmd_start(restrict_dir: Path | None = None) -> StageResult:
    """Start the daemon watcher.

    Args:
        restrict_dir: Optional directory to restrict monitoring to. If None, uses daemon.restrict_dir
            from config, or monitor filter include paths if that is empty string.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Starting daemon...")
        try:
            daemon = Daemon()
            status = daemon.start(restrict_dir=restrict_dir)
            result_obj.result = "Daemon started"
            result_obj.output = DaemonStartOutput(
                errors=[],
                warnings=[],
                message="Daemon started",
                running=bool(getattr(status, "running", False)),
            ).model_dump(mode="python")
            result_obj.success = bool(getattr(status, "running", False))
            yield (1.0, "Complete")
        except Exception as exc:
            result_obj.result = f"Error starting daemon: {exc}"
            result_obj.output = DaemonStartOutput(
                errors=[str(exc)],
                warnings=[],
                message=str(exc),
                running=False,
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")

    return StageResult(
        announce="Starting daemon...",
        progress_callback=do_work,
    )

