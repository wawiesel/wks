"""Execute monitor sync for a given path."""

from pathlib import Path
from typing import Any


def _sync_execute(config, path: Path, recursive: bool) -> dict[str, Any]:
    """Sync a path into the monitor database.

    Currently delegates to the legacy MonitorController; kept local so the
    command file stays minimal and can be swapped out later.
    """
    from ...monitor.controller import MonitorController  # local import to avoid CLI coupling

    return MonitorController.sync_path(config, path, recursive)

