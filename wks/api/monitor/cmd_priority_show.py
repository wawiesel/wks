"""Monitor priority-show API function.

This function lists all priority directories.
Matches CLI: wksc monitor priority show, MCP: wksm_monitor_priority_show
"""

from collections.abc import Iterator
from typing import Any

from wks.utils.normalize_path import normalize_path

from ..StageResult import StageResult
from . import MonitorPriorityShowOutput
from .explain_path import explain_path


def cmd_priority_show() -> StageResult:
    """List all priority directories with their priorities."""

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        priority_directories: dict[str, float],
        validation: dict[str, dict[str, Any]],
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorPriorityShowOutput(
            errors=[],
            warnings=[],
            priority_directories=priority_directories,
            count=len(priority_directories),
            validation=validation,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        yield (0.4, "Validating priority directories...")
        validation: dict[str, dict[str, Any]] = {}
        for i, (path, priority) in enumerate(monitor_cfg.priority.dirs.items()):
            allowed, trace = explain_path(monitor_cfg, normalize_path(path))
            validation[path] = {
                "priority": priority,
                "valid": allowed,
                "error": None if allowed else (trace[-1] if trace else "Excluded by rules"),
            }
            yield (
                0.4 + (i / max(len(monitor_cfg.priority.dirs), 1)) * 0.5,
                f"Validating: {path}...",
            )

        _build_result(
            result_obj,
            success=True,
            message="Priority directories retrieved",
            priority_directories=monitor_cfg.priority.dirs,
            validation=validation,
        )
        yield (1.0, "Complete")

    return StageResult(
        announce="Listing priority directories...",
        progress_callback=do_work,
    )
