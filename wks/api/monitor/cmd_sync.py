"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from pathlib import Path
from typing import Any

import typer

from ..base import StageResult
from ...config import WKSConfig
from ...monitor import MonitorController


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
    path_obj = Path(path).expanduser().resolve()

    # Pre-compute total files for progress reporting
    if path_obj.is_file():
        files_to_process = [path_obj]
    elif recursive and path_obj.exists():
        files_to_process = [p for p in path_obj.rglob("*") if p.is_file()]
    elif path_obj.exists():
        files_to_process = [p for p in path_obj.iterdir() if p.is_file()]
    else:
        files_to_process = []

    total_files = max(len(files_to_process), 1)

    sync_result: dict[str, Any] = {}

    def run_sync(update_fn):
        sync_result.clear()
        sync_result.update(
            MonitorController.sync_path(
                config,
                path_obj,
                recursive,
                progress_cb=update_fn,
            )
        )

    return StageResult(
        announce=f"Syncing {path}...",
        result="Monitor sync completed",
        output=sync_result,
        progress_callback=run_sync,
        progress_total=total_files,
    )
