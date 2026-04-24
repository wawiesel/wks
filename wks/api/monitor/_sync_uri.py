from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from wks.api.config.expand_paths import expand_paths
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.config.write_status_file import write_status_file
from wks.api.database.Database import Database

from . import MonitorSyncOutput
from ._enforce_monitor_db_limit import _enforce_monitor_db_limit
from .calculate_priority import calculate_priority
from .explain_path import explain_path
from .resolve_remote_uri import resolve_remote_uri


def sync_uri_steps(
    config: WKSConfig,
    uri: URI,
    recursive: bool = False,
    *,
    write_status: bool = True,
) -> Generator[tuple[float, str], None, Any]:
    from wks.api.config.file_checksum import file_checksum

    monitor_cfg = config.monitor
    database_name = "nodes"

    yield (0.2, "Resolving path...")
    try:
        path_obj = uri.path
    except ValueError:
        yield (1.0, "Failed")
        return MonitorSyncOutput(
            success=False,
            message=f"Only file URIs are supported. Got {uri}",
            errors=[f"Only file URIs are supported. Got {uri}"],
            warnings=[],
            files_synced=0,
            files_skipped=0,
        )

    if not path_obj.exists():
        yield (0.3, "Path missing; removing from monitor DB...")
        with Database(config.database, database_name) as database:
            database.delete_many({"local_uri": str(URI.from_path(path_obj))})

        output = MonitorSyncOutput(
            success=True,
            message=f"Removed {path_obj.name} from monitor DB",
            errors=[],
            warnings=[],
            files_synced=0,
            files_skipped=0,
        )
        yield (1.0, "Complete")
        if write_status:
            _write_sync_status(config, output)
        return output

    yield (0.3, "Collecting files to process...")
    files_to_process = list(expand_paths(path_obj, recursive=recursive))
    files_to_process.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    files_synced = 0
    files_skipped = 0
    errors: list[str] = []
    warnings: list[str] = []

    yield (0.4, f"Processing {len(files_to_process)} file(s)...")
    with Database(config.database, database_name) as database:
        for index, file_path in enumerate(files_to_process):
            progress = 0.4 + (index / max(len(files_to_process), 1)) * 0.5

            if not explain_path(monitor_cfg, file_path)[0]:
                files_skipped += 1
                database.delete_many({"local_uri": str(URI.from_path(file_path))})
                yield (progress, f"Skipping excluded file: {file_path.name}...")
                continue

            try:
                stat = file_path.stat()
                checksum = file_checksum(file_path)
                priority = calculate_priority(
                    file_path,
                    monitor_cfg.priority.dirs,
                    monitor_cfg.priority.weights.model_dump(),
                )

                if priority < monitor_cfg.min_priority:
                    files_skipped += 1
                    yield (progress, f"Skipping low priority: {file_path.name}...")
                    continue

                path_uri = str(URI.from_path(file_path))
                remote_uri_obj = resolve_remote_uri(URI.from_path(file_path), monitor_cfg.remote)
                remote_uri = str(remote_uri_obj) if remote_uri_obj else None

                database.update_one(
                    {"local_uri": path_uri},
                    {
                        "$set": {
                            "local_uri": path_uri,
                            "remote_uri": remote_uri,
                            "checksum": checksum,
                            "bytes": stat.st_size,
                            "priority": priority,
                            "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    },
                    upsert=True,
                )
                files_synced += 1
                yield (progress, f"Synced: {file_path.name}...")
            except Exception as exc:
                errors.append(f"{file_path}: {exc}")
                files_skipped += 1
                yield (progress, f"Error: {file_path.name}...")

        yield (0.9, "Enforcing database limits...")
        _enforce_monitor_db_limit(database, monitor_cfg.max_documents, monitor_cfg.min_priority)
        database.update_one(
            {"_id": "__meta__"},
            {"$set": {"_id": "__meta__", "doc_type": "meta", "last_sync": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    success = len(errors) == 0
    message = (
        f"Synced {files_synced} file(s), skipped {files_skipped}"
        if success
        else f"Synced {files_synced} file(s), skipped {files_skipped}, {len(errors)} error(s)"
    )
    output = MonitorSyncOutput(
        success=success,
        message=message,
        errors=errors,
        warnings=warnings,
        files_synced=files_synced,
        files_skipped=files_skipped,
    )
    yield (1.0, "Complete")
    if write_status:
        _write_sync_status(config, output)
    return output


def sync_uri(
    config: WKSConfig,
    uri: URI,
    recursive: bool = False,
    *,
    write_status: bool = True,
) -> Any:
    generator = sync_uri_steps(config, uri, recursive=recursive, write_status=write_status)
    while True:
        try:
            next(generator)
        except StopIteration as exc:
            return exc.value


def _write_sync_status(config: WKSConfig, output: Any) -> None:
    write_status_file(
        {
            "database": "nodes",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files_synced": output.files_synced,
            "files_skipped": output.files_skipped,
            "success": output.success,
        },
        wks_home=config.get_config_path().parent,
        filename="monitor.json",
    )
