from collections.abc import Iterator
from contextlib import suppress

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import ServiceClearOutput


def cmd_clear() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        home = WKSConfig.get_home_dir()
        removed: list[str] = []

        yield (0.4, "Clearing daemon status file...")
        daemon_file = home / "daemon.json"
        if daemon_file.exists():
            with suppress(OSError):
                daemon_file.unlink()
                removed.append(str(daemon_file))

        yield (0.7, "Clearing stale lock file...")
        lock_file = home / "daemon.lock"
        if lock_file.exists():
            with suppress(OSError):
                lock_file.unlink()
                removed.append(str(lock_file))

        msg = f"Cleared: {', '.join(removed)}" if removed else "Nothing to clear"

        yield (1.0, "Complete")
        result_obj.result = msg
        result_obj.output = ServiceClearOutput(
            errors=[],
            warnings=[],
            cleared=bool(removed),
            message=msg,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Clearing service errors...",
        progress_callback=do_work,
    )
