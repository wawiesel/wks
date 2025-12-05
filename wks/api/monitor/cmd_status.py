"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from pathlib import Path
from typing import Any

from ..base import StageResult
from ...db_helpers import connect_to_mongo, parse_database_key
from .explain_path import explain_path


def cmd_status() -> StageResult:
    """Get filesystem monitoring status and configuration."""
    from ...config import WKSConfig

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    # Count tracked files via DB helpers
    total_files = 0
    try:
        mongo_uri = config.mongo.uri  # type: ignore[attr-defined]
        db_name, coll_name = parse_database_key(monitor_cfg.sync.database)
        client = connect_to_mongo(mongo_uri)
        collection = client[db_name][coll_name]
        total_files = collection.count_documents({})
    except Exception:
        total_files = 0
    finally:
        try:
            client.close()  # type: ignore[name-defined]
        except Exception:
            pass

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
            issues.append(f"Managed directory invalid: {path} ({err})")

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

    # Build structured output with _tables key for custom formatting
    result = {
        "_tables": [
            # Summary table
            {
                "data": [
                    {"Metric": "Tracked Files", "Value": total_files},
                    {"Metric": "Issues", "Value": len(issues)},
                    {"Metric": "Priority Directories", "Value": len(priority_directories)},
                ],
                "headers": ["Metric", "Value"],
                "title": "Summary",
            },
            # Priority directories table
            {
                "data": priority_dir_rows,
                "headers": ["Path", "Priority", "Valid", "Error"],
                "title": "Priority Directories",
            },
        ],
        "tracked_files": total_files,
        "issues": issues,
        "priority_directories": priority_directories,
        "success": len(issues) == 0,
    }

    # Add filter tables only if they have content
    if monitor_cfg.include_paths:
        result["_tables"].append(
            {
                "data": [{"Path": p} for p in monitor_cfg.include_paths],
                "headers": ["Path"],
                "title": "Include Paths",
            }
        )
    if monitor_cfg.exclude_paths:
        result["_tables"].append(
            {
                "data": [{"Path": p} for p in monitor_cfg.exclude_paths],
                "headers": ["Path"],
                "title": "Exclude Paths",
            }
        )
    if monitor_cfg.include_dirnames:
        result["_tables"].append(
            {
                "data": [{"Directory": d} for d in monitor_cfg.include_dirnames],
                "headers": ["Directory"],
                "title": "Include Dirnames",
            }
        )
    if monitor_cfg.exclude_dirnames:
        result["_tables"].append(
            {
                "data": [{"Directory": d} for d in monitor_cfg.exclude_dirnames],
                "headers": ["Directory"],
                "title": "Exclude Dirnames",
            }
        )
    if monitor_cfg.include_globs:
        result["_tables"].append(
            {
                "data": [{"Pattern": g} for g in monitor_cfg.include_globs],
                "headers": ["Pattern"],
                "title": "Include Globs",
            }
        )
    if monitor_cfg.exclude_globs:
        result["_tables"].append(
            {
                "data": [{"Pattern": g} for g in monitor_cfg.exclude_globs],
                "headers": ["Pattern"],
                "title": "Exclude Globs",
            }
        )

    # Add issues table if there are any
    if issues:
        result["_tables"].append(
            {
                "data": [{"Issue": issue} for issue in issues],
                "headers": ["Issue"],
                "title": "Issues",
            }
        )

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
