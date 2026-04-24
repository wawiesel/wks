from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

from wks.api.config.write_status_file import write_status_file

from ..config.StageResult import StageResult
from ..database.Database import Database
from . import MonitorStatusOutput


def cmd_status() -> StageResult:
    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        database: str,
        tracked_files: int,
        issues: list[str],
        time_based_counts: dict[str, int],
        last_sync: str | None,
        wks_home: Path,
        errors: list[str] | None = None,
    ) -> None:
        output = MonitorStatusOutput(
            errors=errors or [],
            warnings=[],
            database=database,
            tracked_files=tracked_files,
            issues=issues,
            time_based_counts=time_based_counts,
            last_sync=last_sync,
            success=success,
        )

        write_status_file(output.model_dump(mode="python"), wks_home=wks_home, filename="monitor.json")

        result_obj.output = output.model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        wks_home = WKSConfig.get_home_dir()

        database_name = "nodes"

        yield (0.2, "Querying database...")
        total_files = 0
        time_based_counts: dict[str, int] = {}
        last_sync: str | None = None

        errors: list[str] = []
        try:
            with Database(config.database, database_name) as database:
                total_files = database.count_documents({"local_uri": {"$exists": True}})

                meta = database.find_one({"_id": "__meta__"})
                if meta:
                    last_sync = meta["last_sync"]

                yield (0.4, "Calculating time-based statistics...")
                now = datetime.now()
                time_ranges = [
                    ("Last minute", timedelta(minutes=1)),
                    ("Last hour", timedelta(hours=1)),
                    ("1-4 hours", timedelta(hours=4)),
                    ("4-8 hours", timedelta(hours=8)),
                    ("8-24 hours", timedelta(days=1)),
                    ("1-3 days", timedelta(days=3)),
                    ("3-7 days", timedelta(days=7)),
                    ("1-2 weeks", timedelta(weeks=2)),
                    ("2-4 weeks", timedelta(days=30)),
                    ("1-3 months", timedelta(days=90)),
                    ("3-6 months", timedelta(days=180)),
                    ("6-12 months", timedelta(days=365)),
                ]

                prev_cutoff_iso = now.isoformat()  # Start from now
                for i, (label, delta) in enumerate(time_ranges):
                    cutoff = now - delta
                    cutoff_iso = cutoff.isoformat()
                    count = database.count_documents({"timestamp": {"$gte": cutoff_iso, "$lt": prev_cutoff_iso}})
                    time_based_counts[label] = count
                    prev_cutoff_iso = cutoff_iso  # Move window
                    yield (
                        0.4 + (i / len(time_ranges)) * 0.2,
                        f"Processing time range: {label}...",
                    )

                one_year_ago = (now - timedelta(days=365)).isoformat()
                time_based_counts[">1 year"] = database.count_documents({"timestamp": {"$lt": one_year_ago}})

        except Exception as e:
            errors.append(f"Database error: {e}")

        yield (1.0, "Complete")

        issues: list[str] = []
        success = len(errors) == 0
        message = "Monitor status retrieved" if success else f"Monitor status retrieved with {len(errors)} error(s)"

        _build_result(
            result_obj,
            success=success,
            message=message,
            database=database_name,
            tracked_files=total_files,
            issues=issues,
            time_based_counts=time_based_counts,
            last_sync=last_sync,
            wks_home=wks_home,
            errors=errors,
        )

    return StageResult(
        announce="Checking monitor status...",
        progress_callback=do_work,
    )
