"""Top-level status command - aggregates status from all subsystems."""

from collections.abc import Iterator

from wks.services.status import collect_status

from .config.StageResult import StageResult


def cmd_status() -> StageResult:
    """Get aggregated status from all subsystems."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.2, "Collecting subsystem status...")
        response = collect_status()
        yield (1.0, "Complete")
        result_obj.output = response.sections
        result_obj.result = response.message
        result_obj.success = response.success

    return StageResult(
        announce="Checking system status...",
        progress_callback=do_work,
    )
