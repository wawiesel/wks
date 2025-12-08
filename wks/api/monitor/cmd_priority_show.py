"""Monitor priority-show API function.

This function lists all managed directories.
Matches CLI: wksc monitor priority show, MCP: wksm_monitor_priority_show
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from .explain_path import explain_path


def cmd_priority_show() -> StageResult:
    """List all priority directories with their priorities."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        yield (0.4, "Validating priority directories...")
        validation: dict[str, dict[str, Any]] = {}
        for i, (path, priority) in enumerate(monitor_cfg.priority.dirs.items()):
            allowed, trace = explain_path(monitor_cfg, Path(path).expanduser().resolve())
            validation[path] = {
                "priority": priority,
                "valid": allowed,
                "error": None if allowed else (trace[-1] if trace else "Excluded by rules"),
            }
            yield (0.4 + (i / max(len(monitor_cfg.priority.dirs), 1)) * 0.5, f"Validating: {path}...")

        yield (1.0, "Complete")
        result = {
            "priority_directories": monitor_cfg.priority.dirs,
            "count": len(monitor_cfg.priority.dirs),
            "validation": validation,
        }
        result_obj.result = "Priority directories retrieved"
        result_obj.output = result
        result_obj.success = True

    return StageResult(
        announce="Listing priority directories...",
        progress_callback=do_work,
    )
