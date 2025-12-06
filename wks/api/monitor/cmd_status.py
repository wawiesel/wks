"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..base import StageResult
from ..db.DbCollection import DbCollection
from .explain_path import explain_path


def cmd_status() -> StageResult:
    """Get filesystem monitoring status (not configuration - use 'wksc config monitor' for config)."""
    from ...api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    # Count tracked files and time-based statistics via DB API
    total_files = 0
    time_based_counts: dict[str, int] = {}
    try:
        with DbCollection(config.db, monitor_cfg.database) as collection:
            total_files = collection.count_documents({})

            # Calculate time ranges
            now = datetime.now()
            time_ranges = [
                ("Last hour", timedelta(hours=1)),
                ("4 hours", timedelta(hours=4)),
                ("8 hours", timedelta(hours=8)),
                ("1 day", timedelta(days=1)),
                ("3 days", timedelta(days=3)),
                ("7 days", timedelta(days=7)),
                ("2 weeks", timedelta(weeks=2)),
                ("1 month", timedelta(days=30)),
                ("3 months", timedelta(days=90)),
                ("6 months", timedelta(days=180)),
                ("1 year", timedelta(days=365)),
            ]

            # Count files in each time range
            for label, delta in time_ranges:
                cutoff = now - delta
                cutoff_iso = cutoff.isoformat()
                # Query for files with timestamp >= cutoff (modified within the range)
                count = collection.count_documents({"timestamp": {"$gte": cutoff_iso}})
                time_based_counts[label] = count

            # Count files older than 1 year
            one_year_ago = (now - timedelta(days=365)).isoformat()
            time_based_counts[">1 year"] = collection.count_documents({"timestamp": {"$lt": one_year_ago}})

    except Exception:
        total_files = 0
        time_based_counts = {}

    # Validate priority directories
    issues: list[str] = []
    priority_directories: dict[str, dict[str, Any]] = {}

    for path, priority in monitor_cfg.priority.dirs.items():
        managed_resolved = Path(path).expanduser().resolve()
        allowed, trace = explain_path(monitor_cfg, managed_resolved)
        err = None if allowed else (trace[-1] if trace else "Excluded by monitor rules")
        priority_directories[path] = {
            "priority": priority,
            "valid": allowed,
            "error": err,
        }
        if err:
            issues.append(f"Priority directory invalid: {path} ({err})")

    # Only include status-specific data (not config that can be retrieved elsewhere)
    result = {
        "tracked_files": total_files,
        "issues": issues,
        "priority_directories": priority_directories,  # Includes validation status (status-specific)
        "time_based_counts": time_based_counts,
        "success": len(issues) == 0,
    }

    result_msg = f"Monitor status retrieved ({len(issues)} issue(s) found)" if issues else "Monitor status retrieved"

    return StageResult(
        announce="Checking monitor status...",
        result=result_msg,
        output=result,
    )
