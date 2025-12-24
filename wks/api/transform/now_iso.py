"""ISO timestamp helper."""

from datetime import datetime, timezone


def now_iso() -> str:
    """Get current time as ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()
