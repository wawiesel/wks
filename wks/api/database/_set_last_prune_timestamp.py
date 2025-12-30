"""Set last prune timestamp."""

import contextlib
import json
from datetime import datetime, timezone

from ._get_status_path import _get_status_path


def set_last_prune_timestamp(database_name: str, timestamp: datetime | None = None) -> None:
    """Set last prune timestamp for a database.

    Args:
        database_name: Name of database (e.g., "transform", "nodes")
        timestamp: Timestamp to set (default: now)
    """
    status_path = _get_status_path()

    # Load existing data
    data: dict = {}
    if status_path.exists():
        with contextlib.suppress(Exception):
            data = json.loads(status_path.read_text())

    # Ensure prune_timestamps dict exists
    if "prune_timestamps" not in data:
        data["prune_timestamps"] = {}

    # Set timestamp
    ts = timestamp or datetime.now(timezone.utc)
    data["prune_timestamps"][database_name] = ts.isoformat()

    # Write back
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(data, indent=2))
