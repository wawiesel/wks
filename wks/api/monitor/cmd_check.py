"""Monitor check API function.

This function checks if a path would be monitored and calculates its priority.
Matches CLI: wksc monitor check <path>, MCP: wksm_monitor_check
"""

from pathlib import Path

import typer

from ...config import WKSConfig
from ..base import StageResult
from .explain_path import explain_path
from .calculate_priority import calculate_priority


def cmd_check(
    path: str | None = typer.Argument(None, help="File or directory path to check"),
) -> StageResult:
    """Check if a path would be monitored and calculate its priority."""
    config = WKSConfig.load()
    monitor_cfg = config.monitor

    test_path = Path(path).expanduser().resolve()
    path_exists = test_path.exists()

    allowed, trace = explain_path(monitor_cfg, test_path)

    # Build decision list from trace messages and path existence
    decisions: list[dict[str, str]] = []
    decisions.append(
        {
            "symbol": "✓" if path_exists else "⚠",
            "message": f"Path exists: {test_path}" if path_exists else f"Path does not exist (checking as if it did): {test_path}",
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

    return StageResult(
        announce=f"Checking if path would be monitored: {path}",
        result=res_msg,
        output=output,
        success=output["success"],
    )
