"""Monitor status API function.

This function provides filesystem monitoring status and configuration.
Matches CLI: wksc monitor status, MCP: wksm_monitor_status
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..database.Database import Database
from ..StageResult import StageResult
from . import MonitorStatusOutput
from ._write_status_file import write_status_file
from .explain_path import explain_path


def cmd_status() -> StageResult:
    """Get filesystem monitoring status (not configuration - use 'wksc config monitor' for config)."""

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        database: str,
        tracked_files: int,
        issues: list[str],
        priority_directories: list[dict[str, Any]],
        time_based_counts: dict[str, int],
        last_sync: str | None,
        wks_home: Path,
    ) -> None:
        """Helper to build and assign the output result."""
        output = MonitorStatusOutput(
            errors=[],
            warnings=[],
            database=database,
            tracked_files=tracked_files,
            issues=issues,
            priority_directories=priority_directories,
            time_based_counts=time_based_counts,
            last_sync=last_sync,
            success=success,
        ).model_dump(mode="python")

        # Write status file
        write_status_file(output, wks_home=wks_home)

        result_obj.output = output
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor
        wks_home = WKSConfig.get_home_dir()

        # Compute database name from prefix
        database_name = f"{config.database.prefix}.monitor"

        # Count tracked files and time-based statistics via DB API
        yield (0.2, "Querying database...")
        total_files = 0
        time_based_counts: dict[str, int] = {}
        last_sync: str | None = None

        try:
            with Database(config.database, database_name) as database:
                total_files = database.count_documents({})

                # Get last sync timestamp from meta document
                meta = database.find_one({"_id": "__meta__"})
                if meta:
                    last_sync = meta.get("last_sync")

                # Calculate time ranges
                yield (0.4, "Calculating time-based statistics...")
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
                for i, (label, delta) in enumerate(time_ranges):
                    cutoff = now - delta
                    cutoff_iso = cutoff.isoformat()
                    # Query for files with timestamp >= cutoff (modified within the range)
                    count = database.count_documents({"timestamp": {"$gte": cutoff_iso}})
                    time_based_counts[label] = count
                    yield (
                        0.4 + (i / len(time_ranges)) * 0.2,
                        f"Processing time range: {label}...",
                    )

                # Count files older than 1 year
                one_year_ago = (now - timedelta(days=365)).isoformat()
                time_based_counts[">1 year"] = database.count_documents({"timestamp": {"$lt": one_year_ago}})

        except Exception:
            total_files = 0
            time_based_counts = {}

        # Validate priority directories
        yield (0.7, "Validating priority directories...")
        issues: list[str] = []
        priority_directories: list[dict[str, Any]] = []

        for i, (path, priority) in enumerate(monitor_cfg.priority.dirs.items()):
            managed_resolved = Path(path).expanduser().resolve()
            allowed, trace = explain_path(monitor_cfg, managed_resolved)
            err = None if allowed else (trace[-1] if trace else "Excluded by monitor rules")
            priority_directories.append(
                {
                    "path": path,
                    "priority": priority,
                    "valid": allowed,
                    "error": err,
                }
            )
            if err:
                issues.append(f"Priority directory invalid: {path} ({err})")
            yield (
                0.7 + (i / max(len(monitor_cfg.priority.dirs), 1)) * 0.2,
                f"Validating: {path}...",
            )

        # Only include status-specific data (not config that can be retrieved elsewhere)
        yield (1.0, "Complete")

        message = f"Monitor status retrieved ({len(issues)} issue(s) found)" if issues else "Monitor status retrieved"

        _build_result(
            result_obj,
            success=len(issues) == 0,
            message=message,
            database=database_name,
            tracked_files=total_files,
            issues=issues,
            priority_directories=priority_directories,
            time_based_counts=time_based_counts,
            last_sync=last_sync,
            wks_home=wks_home,
        )

    return StageResult(
        announce="Checking monitor status...",
        progress_callback=do_work,
    )
