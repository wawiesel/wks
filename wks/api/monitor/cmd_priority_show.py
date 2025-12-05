"""Monitor priority-show API function.

This function lists all managed directories.
Matches CLI: wksc monitor priority show, MCP: wksm_monitor_priority_show
"""

from pathlib import Path
from typing import Any

from ...config import WKSConfig
from ..base import StageResult
from .explain_path import explain_path


def cmd_priority_show() -> StageResult:
    """List all priority directories with their priorities."""
    config = WKSConfig.load()
    monitor_cfg = config.monitor

    validation: dict[str, dict[str, Any]] = {}
    for path, priority in monitor_cfg.priority.dirs.items():
        allowed, trace = explain_path(monitor_cfg, Path(path).expanduser().resolve())
        validation[path] = {
            "priority": priority,
            "valid": allowed,
            "error": None if allowed else (trace[-1] if trace else "Excluded by rules"),
        }

    result = {
        "priority_directories": monitor_cfg.priority.dirs,
        "count": len(monitor_cfg.priority.dirs),
        "validation": validation,
    }

    return StageResult(
        announce="Listing priority directories...",
        result="Priority directories retrieved",
        output=result,
    )
