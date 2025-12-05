"""Monitor check API function.

This function checks if a path would be monitored and calculates its priority.
Matches CLI: wksc monitor check <path>, MCP: wksm_monitor_check
"""

from pathlib import Path

import typer

from ...config import WKSConfig
from ..base import StageResult
from ._check_build_decisions import _check_build_decisions
from .calculate_priority import calculate_priority
from .MonitorRules import MonitorRules


def cmd_check(
    path: str = typer.Argument(..., help="File or directory path to check"),
) -> StageResult:
    """Check if a path would be monitored and calculate its priority."""
    config = WKSConfig.load()
    monitor_cfg = config.monitor
    rules = MonitorRules.from_config(monitor_cfg)

    test_path = Path(path).expanduser().resolve()
    path_exists = test_path.exists()

    allowed, trace = rules.explain(test_path)
    decisions = _check_build_decisions(trace, path_exists, test_path)

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
