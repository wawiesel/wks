"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from ..database.Database import Database
from ..StageResult import StageResult
from . import MonitorSyncOutput
from ._enforce_monitor_db_limit import _enforce_monitor_db_limit
from .calculate_priority import calculate_priority
from .explain_path import explain_path


def cmd_sync(
    path: str,
    recursive: bool = False,
) -> StageResult:
    """Force update of file or directory into monitor database.

    Args:
        path: File or directory path to sync
        recursive: Whether to recursively process directories

    Returns:
        StageResult with sync results (files_synced, files_skipped, errors)
    """

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        files_synced: int,
        files_skipped: int,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorSyncOutput(
            errors=errors or [],
            warnings=warnings or [],
            success=success,
            message=message,
            files_synced=files_synced,
            files_skipped=files_skipped,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ...utils import file_checksum
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        yield (0.2, "Resolving path...")
        path_obj = Path(path).expanduser().resolve()
        if not path_obj.exists():
            yield (0.3, "Path missing; removing from monitor DB...")

            with Database(config.database, monitor_cfg.database) as database:
                try:
                    database.delete_many({"path": path_obj.as_uri()})
                finally:
                    pass
            warn_msg = f"Removed missing path from monitor DB: {path_obj}"
            warning_list = [warn_msg]

            yield (1.0, "Complete")
            _build_result(
                result_obj,
                success=True,
                message=warn_msg,
                errors=[],
                warnings=warning_list,
                files_synced=0,
                files_skipped=0,
            )
            return

        yield (0.3, "Collecting files to process...")
        files_to_process: list[Path]
        if path_obj.is_file():
            files_to_process = [path_obj]
        elif recursive:
            files_to_process = [p for p in path_obj.rglob("*") if p.is_file()]
        else:
            files_to_process = [p for p in path_obj.iterdir() if p.is_file()]

        files_synced = 0
        files_skipped = 0
        errors: list[str] = []
        warnings: list[str] = []

        yield (0.4, f"Processing {len(files_to_process)} file(s)...")
        with Database(config.database, monitor_cfg.database) as database:
            try:
                for i, file_path in enumerate(files_to_process):
                    if not explain_path(monitor_cfg, file_path)[0]:
                        files_skipped += 1
                        yield (
                            0.4 + (i / max(len(files_to_process), 1)) * 0.5,
                            f"Skipping excluded file: {file_path.name}...",
                        )
                        continue

                    try:
                        stat = file_path.stat()
                        checksum = file_checksum(file_path)
                        now = datetime.now()

                        priority = calculate_priority(
                            file_path,
                            monitor_cfg.priority.dirs,
                            monitor_cfg.priority.weights.model_dump(),
                        )

                        # Skip files below min_priority
                        if priority < monitor_cfg.sync.min_priority:
                            files_skipped += 1
                            yield (
                                0.4 + (i / max(len(files_to_process), 1)) * 0.5,
                                f"Skipping low priority: {file_path.name}...",
                            )
                            continue

                        path_uri = file_path.as_uri()
                        # Check if file content changed (checksum comparison)
                        existing_doc = database.find_one({"path": path_uri}, {"checksum": 1, "timestamp": 1})
                        timestamp = now.isoformat()
                        # If file unchanged (same checksum), preserve existing timestamp
                        if existing_doc and existing_doc.get("checksum") == checksum:
                            timestamp = existing_doc.get("timestamp", timestamp)

                        doc = {
                            "path": path_uri,
                            "checksum": checksum,
                            "bytes": stat.st_size,
                            "priority": priority,
                            "timestamp": timestamp,
                        }

                        database.update_one({"path": doc["path"]}, {"$set": doc}, upsert=True)
                        files_synced += 1
                        yield (
                            0.4 + (i / max(len(files_to_process), 1)) * 0.5,
                            f"Synced: {file_path.name}...",
                        )
                    except Exception as exc:
                        errors.append(f"{file_path}: {exc}")
                        files_skipped += 1
                        yield (
                            0.4 + (i / max(len(files_to_process), 1)) * 0.5,
                            f"Error: {file_path.name}...",
                        )
            finally:
                yield (0.9, "Enforcing database limits...")
                _enforce_monitor_db_limit(database, monitor_cfg.sync.max_documents, monitor_cfg.sync.min_priority)

        success = len(errors) == 0
        result_msg = (
            f"Synced {files_synced} file(s), skipped {files_skipped}"
            if success
            else f"Synced {files_synced} file(s), skipped {files_skipped}, {len(errors)} error(s)"
        )

        yield (1.0, "Complete")

        _build_result(
            result_obj,
            success=success,
            message=result_msg,
            files_synced=files_synced,
            files_skipped=files_skipped,
            errors=errors,
            warnings=warnings,
        )

    return StageResult(
        announce=f"Syncing {path}...",
        progress_callback=do_work,
    )
