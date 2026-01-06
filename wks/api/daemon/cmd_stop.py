"""Stop daemon (background watcher)."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import DaemonStopOutput
from .Daemon import Daemon


def cmd_stop() -> StageResult:
    """Stop the daemon watcher."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Stopping daemon...")
        try:
            daemon = Daemon()
            status = daemon.stop()
            result_obj.result = "Daemon stopped"
            result_obj.output = DaemonStopOutput(
                errors=[],
                warnings=[],
                message="Daemon stopped",
                stopped=not bool(getattr(status, "running", True)),
            ).model_dump(mode="python")
            result_obj.success = True
            yield (1.0, "Complete")
        except Exception as exc:
            result_obj.result = f"Error stopping daemon: {exc}"
            result_obj.output = DaemonStopOutput(
                errors=[str(exc)],
                warnings=[],
                message=str(exc),
                stopped=False,
            ).model_dump(mode="python")
            result_obj.success = False
            yield (1.0, "Complete")

    return StageResult(
        announce="Stopping daemon...",
        progress_callback=do_work,
    )
