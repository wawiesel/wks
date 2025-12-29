"""Prune timer utilities for per-database prune tracking."""

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _get_status_path() -> Path:
    """Get path to database status file."""
    import os

    wks_home = os.environ.get("WKS_HOME", str(Path.home() / ".wks"))
    return Path(wks_home) / "database.json"


def get_last_prune_timestamp(database_name: str) -> datetime | None:
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


def should_prune(database_name: str, prune_frequency_secs: float) -> bool:
    """Check if database should be pruned based on timer.

    Args:
        database_name: Name of database
        prune_frequency_secs: Configured prune frequency (0 = disabled)

    Returns:
        True if prune should run
    """
    if prune_frequency_secs <= 0:
        return False

    last_prune = get_last_prune_timestamp(database_name)
    if last_prune is None:
        return True  # Never pruned

    now = datetime.now(timezone.utc)
    elapsed = (now - last_prune).total_seconds()
    return elapsed >= prune_frequency_secs
