"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from wks.api.config.write_status_file import write_status_file
from wks.utils.expand_paths import expand_paths
from wks.utils.path_to_uri import path_to_uri

from ..database.Database import Database
from ..StageResult import StageResult
from . import MonitorSyncOutput
from ._enforce_monitor_db_limit import _enforce_monitor_db_limit
from .calculate_priority import calculate_priority
from .explain_path import explain_path
from .resolve_remote_uri import resolve_remote_uri


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

        # Collection name: 'nodes'
        database_name = "nodes"
        wks_home = WKSConfig.get_home_dir()

        yield (0.2, "Resolving path...")
        path_obj = Path(path).expanduser().resolve()
        if not path_obj.exists():
            yield (0.3, "Path missing; removing from monitor DB...")

            with Database(config.database, database_name) as database:
                try:
                    database.delete_many({"local_uri": path_to_uri(path_obj)})
                finally:
                    pass

            # File deletions are silent - no warning needed
            yield (1.0, "Complete")
            _build_result(
                result_obj,
                success=True,
                message=f"Removed {path_obj.name} from monitor DB",
                errors=[],
                warnings=[],
                files_synced=0,
                files_skipped=0,
            )
            return

        yield (0.3, "Collecting files to process...")
        files_to_process: list[Path] = list(expand_paths(path_obj, recursive=recursive))

        files_synced = 0
        files_skipped = 0
        errors: list[str] = []
        warnings: list[str] = []

        yield (0.4, f"Processing {len(files_to_process)} file(s)...")
        with Database(config.database, database_name) as database:
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

                        priority = calculate_priority(
                            file_path,
                            monitor_cfg.priority.dirs,
                            monitor_cfg.priority.weights.model_dump(),
                        )

                        # Skip files below min_priority
                        if priority < monitor_cfg.min_priority:
                            files_skipped += 1
                            yield (
                                0.4 + (i / max(len(files_to_process), 1)) * 0.5,
                                f"Skipping low priority: {file_path.name}...",
                            )
                            continue

                        path_uri = path_to_uri(file_path)

                        # Use file's last modified time (st_mtime)
                        timestamp = datetime.fromtimestamp(stat.st_mtime).isoformat()

                        # Resolve remote URI
                        remote_uri = resolve_remote_uri(file_path, monitor_cfg.remote)

                        doc = {
                            "local_uri": path_uri,
                            "remote_uri": remote_uri,
                            "checksum": checksum,
                            "bytes": stat.st_size,
                            "priority": priority,
                            "timestamp": timestamp,
                        }

                        database.update_one({"local_uri": doc["local_uri"]}, {"$set": doc}, upsert=True)
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
                _enforce_monitor_db_limit(database, monitor_cfg.max_documents, monitor_cfg.min_priority)

                # Update meta document with last_sync timestamp
                sync_time = datetime.now(timezone.utc).isoformat()
                database.update_one(
                    {"_id": "__meta__"},
                    {"$set": {"_id": "__meta__", "doc_type": "meta", "last_sync": sync_time}},
                    upsert=True,
                )

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

        # Write status file after sync

        output = {
            "database": database_name,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files_synced": files_synced,
            "files_skipped": files_skipped,
            "success": success,
        }
        write_status_file(output, wks_home=wks_home, filename="monitor.json")

    return StageResult(
        announce=f"Syncing {path}...",
        progress_callback=do_work,
    )
