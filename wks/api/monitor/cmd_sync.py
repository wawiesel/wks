"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from pathlib import Path

import typer

from ..base import StageResult
from ...config import WKSConfig
from ...monitor_rules import MonitorRules
from ...priority import calculate_priority
from ...utils import file_checksum


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
    from datetime import datetime

    from pymongo import MongoClient

    config = WKSConfig.load()
    path_obj = Path(path).expanduser().resolve()

    # Check if path exists
    if not path_obj.exists():
        return StageResult(
            announce=f"Syncing {path}...",
            result=f"Path does not exist: {path}",
            output={"success": False, "message": f"Path does not exist: {path}", "files_synced": 0, "files_skipped": 0, "errors": []},
            success=False,
        )

    # Get monitor rules
    rules = MonitorRules.from_config(config.monitor)

    # Connect to database
    db_name, collection_name = config.monitor.database.split(".", 1)
    client = MongoClient(config.db.uri)
    db = client[db_name]
    monitor_collection = db[collection_name]

    files_synced = 0
    files_skipped = 0
    errors: list[str] = []

    # Process files
    if path_obj.is_file():
        # Single file
        files_to_process = [path_obj]
    elif recursive:
        # Recursive directory traversal
        files_to_process = [p for p in path_obj.rglob("*") if p.is_file()]
    else:
        # Non-recursive: only files directly in directory
        files_to_process = [p for p in path_obj.iterdir() if p.is_file()]

    # Progress callback for long operations
    total_files = len(files_to_process)

    def progress_callback(update_fn):
        nonlocal files_synced, files_skipped, errors
        processed = 0
        for file_path in files_to_process:
            # Check if should be ignored
            if not rules.allows(file_path):
                files_skipped += 1
                processed += 1
                update_fn(f"Processing {file_path.name}...", processed / total_files if total_files > 0 else 0)
                continue

            try:
                stat = file_path.stat()
                checksum = file_checksum(file_path)
                now = datetime.now()

                managed_dirs = config.monitor.managed_directories
                priority_config = config.monitor.priority
                touch_weight = config.monitor.touch_weight

                priority = calculate_priority(file_path, managed_dirs, priority_config)

                path_uri = file_path.as_uri()
                existing_doc = monitor_collection.find_one({"path": path_uri}, {"timestamp": 1, "touches_per_day": 1})

                # Calculate touches_per_day (simplified version)
                touches_per_day = 0.0
                if existing_doc and existing_doc.get("timestamp"):
                    try:
                        last_timestamp = datetime.fromisoformat(existing_doc["timestamp"])
                        interval = (now - last_timestamp).total_seconds()
                        if interval > 0:
                            touches_per_day = 86400.0 / interval
                    except Exception:
                        pass

                doc = {
                    "path": path_uri,
                    "checksum": checksum,
                    "bytes": stat.st_size,
                    "priority": priority,
                    "timestamp": now.isoformat(),
                    "touches_per_day": touches_per_day,
                }

                monitor_collection.update_one({"path": doc["path"]}, {"$set": doc}, upsert=True)
                files_synced += 1
                processed += 1
                update_fn(f"Processing {file_path.name}...", processed / total_files if total_files > 0 else 0)
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
                processed += 1
                update_fn(f"Processing {file_path.name}...", processed / total_files if total_files > 0 else 0)

        client.close()

    result = {
        "success": len(errors) == 0,
        "files_synced": files_synced,
        "files_skipped": files_skipped,
        "errors": errors,
    }

    if len(errors) == 0:
        result_msg = f"Synced {files_synced} file(s), skipped {files_skipped}"
    else:
        result_msg = f"Synced {files_synced} file(s), skipped {files_skipped}, {len(errors)} error(s)"

    return StageResult(
        announce=f"Syncing {path}...",
        result=result_msg,
        output=result,
        progress_callback=progress_callback if total_files > 0 else None,
        success=len(errors) == 0,
    )

