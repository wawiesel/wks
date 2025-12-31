"""Get last prune timestamp."""

import json
from datetime import datetime

from ._get_status_path import _get_status_path


def _get_last_prune_timestamp(database_name: str) -> datetime | None:
    """Get last prune timestamp for a database.

    Args:
        database_name: Name of database (e.g., "transform", "nodes")

    Returns:
        Last prune datetime or None if never pruned
    """
    status_path = _get_status_path()
    if not status_path.exists():
        return None

    try:
        data = json.loads(status_path.read_text())
        timestamps = data.get("prune_timestamps", {})
        ts_str = timestamps.get(database_name)
        if ts_str:
            return datetime.fromisoformat(ts_str)
    except Exception:
        pass
    return None
