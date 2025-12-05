"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..base import StageResult
from ..db.DatabaseCollection import DatabaseCollection
from .explain_path import explain_path


def cmd_status() -> StageResult:
    """Get filesystem monitoring status and configuration."""
    from ...config import WKSConfig

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    # Count tracked files and time-based statistics via DB API
    total_files = 0
    time_based_counts: dict[str, int] = {}
    try:
        with DatabaseCollection(monitor_cfg.sync.database) as collection:
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

    # Format priority directories as a list of dicts for better table display
    priority_dir_rows = [
        {
            "Path": path,
            "Priority": priority_info["priority"],
            "Valid": "✓" if priority_info["valid"] else "✗",
            "Error": priority_info["error"] or "-",
        }
        for path, priority_info in priority_directories.items()
    ]

    # Build combined include/exclude tables
    tables = []

    # Priority directories table
    if priority_dir_rows:
        tables.append(
            {
                "data": priority_dir_rows,
                "headers": ["Path", "Priority", "Valid", "Error"],
                "title": "Priority Directories",
            }
        )

    # Paths table (include/exclude combined)
    max_paths = max(len(monitor_cfg.include_paths), len(monitor_cfg.exclude_paths))
    if max_paths > 0:
        path_rows = []
        for i in range(max_paths):
            row = {
                "Include": monitor_cfg.include_paths[i] if i < len(monitor_cfg.include_paths) else "",
                "Exclude": monitor_cfg.exclude_paths[i] if i < len(monitor_cfg.exclude_paths) else "",
            }
            path_rows.append(row)
        tables.append({"data": path_rows, "headers": ["Include", "Exclude"], "title": "Paths"})

    # Dirnames table (include/exclude combined)
    max_dirnames = max(len(monitor_cfg.include_dirnames), len(monitor_cfg.exclude_dirnames))
    if max_dirnames > 0:
        dirname_rows = []
        for i in range(max_dirnames):
            row = {
                "Include": monitor_cfg.include_dirnames[i] if i < len(monitor_cfg.include_dirnames) else "",
                "Exclude": monitor_cfg.exclude_dirnames[i] if i < len(monitor_cfg.exclude_dirnames) else "",
            }
            dirname_rows.append(row)
        tables.append({"data": dirname_rows, "headers": ["Include", "Exclude"], "title": "Dirnames"})

    # Globs table (include/exclude combined)
    max_globs = max(len(monitor_cfg.include_globs), len(monitor_cfg.exclude_globs))
    if max_globs > 0:
        glob_rows = []
        for i in range(max_globs):
            row = {
                "Include": monitor_cfg.include_globs[i] if i < len(monitor_cfg.include_globs) else "",
                "Exclude": monitor_cfg.exclude_globs[i] if i < len(monitor_cfg.exclude_globs) else "",
            }
            glob_rows.append(row)
        tables.append({"data": glob_rows, "headers": ["Include", "Exclude"], "title": "Globs"})

    # Add issues table if there are any
    if issues:
        tables.append(
            {
                "data": [{"Issue": issue} for issue in issues],
                "headers": ["Issue"],
                "title": "Issues",
            }
        )

    # Summary table (last)
    summary_data = [
        {"Metric": "Tracked Files", "Value": total_files},
        {"Metric": "Issues", "Value": len(issues)},
        {"Metric": "Priority Directories", "Value": len(priority_directories)},
    ]

    # Add time-based file counts
    if time_based_counts:
        summary_data.append({"Metric": "", "Value": ""})  # Separator
        for label in [
            "Last hour",
            "4 hours",
            "8 hours",
            "1 day",
            "3 days",
            "7 days",
            "2 weeks",
            "1 month",
            "3 months",
            "6 months",
            "1 year",
            ">1 year",
        ]:
            count = time_based_counts.get(label, 0)
            summary_data.append({"Metric": f"Modified ({label})", "Value": count})

    tables.append(
        {
            "data": summary_data,
            "headers": ["Metric", "Value"],
            "title": "Summary",
        }
    )

    result = {
        "_tables": tables,
        "tracked_files": total_files,
        "issues": issues,
        "priority_directories": priority_directories,
        "success": len(issues) == 0,
    }

    result_msg = (
        f"Monitor status retrieved ({len(issues)} issue(s) found)"
        if issues
        else "Monitor status retrieved"
    )

    return StageResult(
        announce="Checking monitor status...",
        result=result_msg,
        output=result,
    )
