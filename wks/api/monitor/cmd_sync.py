"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from ...config import WKSConfig
from ...db_helpers import connect_to_mongo, parse_database_key
from ...utils import file_checksum
from ..base import StageResult
from ._enforce_monitor_db_limit import _enforce_monitor_db_limit
from .MonitorRules import MonitorRules
from .calculate_priority import calculate_priority


def cmd_sync(
    path: str = typer.Argument(..., help="File or directory path to sync"),
    recursive: bool = typer.Option(False, "--recursive", help="Recursively process directory"),
) -> StageResult:
    """Force update of file or directory into monitor database.

    Args:
        path: File or directory path to sync
        recursive: Whether to recursively process directories

    Returns:
        StageResult with sync results (files_synced, files_skipped, errors)
    """
    config = WKSConfig.load()
    monitor_cfg = config.monitor
    mongo_uri = config.mongo.uri

    path_obj = Path(path).expanduser().resolve()
    if not path_obj.exists():
        sync_result = {
            "success": False,
            "message": f"Path does not exist: {path_obj}",
            "files_synced": 0,
            "files_skipped": 0,
            "errors": [f"Path does not exist: {path_obj}"],
        }
        return StageResult(
            announce=f"Syncing {path}...",
            result=sync_result.get("message", "Monitor sync completed"),
            output=sync_result,
            success=sync_result.get("success", True),
        )

    rules = MonitorRules.from_config(monitor_cfg)

    try:
        db_name, collection_name = parse_database_key(monitor_cfg.sync.database)
    except ValueError:
        sync_result = {
            "success": False,
            "message": f"Invalid database name: {monitor_cfg.sync.database}",
            "files_synced": 0,
            "files_skipped": 0,
            "errors": [f"Invalid database name: {monitor_cfg.sync.database}"],
        }
        return StageResult(
            announce=f"Syncing {path}...",
            result=sync_result.get("message", "Monitor sync completed"),
            output=sync_result,
            success=sync_result.get("success", True),
        )

    client = connect_to_mongo(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    files_to_process: list[Path]
    if path_obj.is_file():
        files_to_process = [path_obj]
    elif recursive:
        files_to_process = [p for p in path_obj.rglob("*") if p.is_file()]
    else:
        files_to_process = [p for p in path_obj.iterdir() if p.is_file()]

    total_files = len(files_to_process)
    files_synced = 0
    files_skipped = 0
    errors: list[str] = []

    try:
        for idx, file_path in enumerate(files_to_process, start=1):
            if not rules.allows(file_path):
                files_skipped += 1
                continue

            try:
                stat = file_path.stat()
                checksum = file_checksum(file_path)
                now = datetime.now()

                priority = calculate_priority(file_path, monitor_cfg.priority.dirs, monitor_cfg.priority.weights.model_dump())

                # Skip files below min_priority
                if priority < monitor_cfg.sync.min_priority:
                    files_skipped += 1
                    continue

                path_uri = file_path.as_uri()
                # Check if file content changed (checksum comparison)
                existing_doc = collection.find_one({"path": path_uri}, {"checksum": 1, "timestamp": 1})
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

                collection.update_one({"path": doc["path"]}, {"$set": doc}, upsert=True)
                files_synced += 1
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"{file_path}: {exc}")
                files_skipped += 1
    finally:
        _enforce_monitor_db_limit(collection, monitor_cfg.sync.max_documents, monitor_cfg.sync.min_priority)
        client.close()

    success = len(errors) == 0
    result_msg = (
        f"Synced {files_synced} file(s), skipped {files_skipped}"
        if success
        else f"Synced {files_synced} file(s), skipped {files_skipped}, {len(errors)} error(s)"
    )

    sync_result = {
        "success": success,
        "message": result_msg,
        "files_synced": files_synced,
        "files_skipped": files_skipped,
        "errors": errors,
    }

    return StageResult(
        announce=f"Syncing {path}...",
        result=sync_result.get("message", "Monitor sync completed"),
        output=sync_result,
        success=sync_result.get("success", True),
    )
