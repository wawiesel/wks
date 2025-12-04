"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP: wksm_monitor_sync
"""

from pathlib import Path
from typing import Any

import typer

from ...config import WKSConfig
from ...monitor import MonitorController
from ..base import StageResult


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

    sync_result: dict[str, Any] = MonitorController.sync_path(
        config,
        path_obj,
        recursive,
    )

    return StageResult(
        announce=f"Syncing {path}...",
        result=sync_result.get("message", "Monitor sync completed"),
        output=sync_result,
        success=sync_result.get("success", True),
    )
