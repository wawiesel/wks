"""Monitor check API function.

This function checks if a path would be monitored and calculates its priority.
Matches CLI: wksc monitor check <path>, MCP: wksm_monitor_check
"""

from collections.abc import Iterator
from pathlib import Path

from ..StageResult import StageResult
from .calculate_priority import calculate_priority
from .explain_path import explain_path


def cmd_check(path: str) -> StageResult:
    """Check if a path would be monitored and calculate its priority."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        yield (0.4, "Resolving path...")
        test_path = Path(path).expanduser().resolve()
        path_exists = test_path.exists()

        yield (0.6, "Checking monitor rules...")
        allowed, trace = explain_path(monitor_cfg, test_path)

        # Build decision list from trace messages and path existence
        yield (0.7, "Building decision trace...")
        decisions: list[dict[str, str]] = []
        decisions.append(
            {
                "symbol": "✓" if path_exists else "⚠",
                "message": f"Path exists: {test_path}"
                if path_exists
                else f"Path does not exist (checking as if it did): {test_path}",
            }
        )
        for message in trace:
            lower = message.lower()
            if lower.startswith("excluded"):
                symbol = "✗"
            elif "override" in lower or lower.startswith("included"):
                symbol = "✓"
            else:
                symbol = "•"
            decisions.append({"symbol": symbol, "message": message})

        yield (0.9, "Calculating priority...")
        if not allowed:
            output = {
                "path": str(test_path),
                "is_monitored": False,
                "reason": trace[-1] if trace else "Excluded by monitor rules",
                "priority": None,
                "decisions": decisions,
                "success": False,
            }
            res_msg = "Path is not monitored"
        else:
            priority = calculate_priority(test_path, monitor_cfg.priority.dirs, monitor_cfg.priority.weights.model_dump())
            decisions.append({"symbol": "✓", "message": f"Priority calculated: {priority}"})
            output = {
                "path": str(test_path),
                "is_monitored": True,
                "reason": "Would be monitored",
                "priority": priority,
                "decisions": decisions,
                "success": True,
            }
            res_msg = f"Path is monitored with priority {priority}"

        yield (1.0, "Complete")
        result_obj.result = res_msg
        result_obj.output = output
        result_obj.success = output["success"]

    return StageResult(
        announce=f"Checking if path would be monitored: {path}",
        progress_callback=do_work,
    )
