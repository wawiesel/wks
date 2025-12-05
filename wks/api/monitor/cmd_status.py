"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from pathlib import Path
from typing import Any

from ..base import StageResult
from ...db_helpers import connect_to_mongo, parse_database_key
from .MonitorRules import MonitorRules


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
    rules = MonitorRules.from_config(monitor_cfg)
    issues: list[str] = []
    priority_directories: dict[str, dict[str, Any]] = {}

    for path, priority in monitor_cfg.priority.dirs.items():
        managed_resolved = Path(path).expanduser().resolve()
        allowed, trace = rules.explain(managed_resolved)
        err = None if allowed else (trace[-1] if trace else "Excluded by monitor rules")
        priority_directories[path] = {
            "priority": priority,
            "valid": allowed,
            "error": err,
        }
        if err:
            issues.append(f"Managed directory invalid: {path} ({err})")

    result = {
        "tracked_files": total_files,
        "issues": issues,
        "redundancies": [],
        "priority_directories": priority_directories,
        "include_paths": list(monitor_cfg.filter.include_paths),
        "exclude_paths": list(monitor_cfg.filter.exclude_paths),
        "include_dirnames": list(monitor_cfg.filter.include_dirnames),
        "exclude_dirnames": list(monitor_cfg.filter.exclude_dirnames),
        "include_globs": list(monitor_cfg.filter.include_globs),
        "exclude_globs": list(monitor_cfg.filter.exclude_globs),
        "include_dirname_validation": {},
        "exclude_dirname_validation": {},
        "include_glob_validation": {},
        "exclude_glob_validation": {},
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
