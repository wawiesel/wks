from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import WKS_HOME_EXT

_DB_ACTIVITY_DIR = Path.home() / WKS_HOME_EXT
_DB_ACTIVITY_SUMMARY = _DB_ACTIVITY_DIR / "db_activity.json"
_DB_ACTIVITY_HISTORY = _DB_ACTIVITY_DIR / "db_activity_history.json"
_MAX_HISTORY_SECONDS = 24 * 60 * 60  # keep last 24 hours
_MAX_HISTORY_ENTRIES = 2000


def _now() -> float:
    return time.time()


def record_db_activity(operation: str, detail: Optional[str] = None) -> None:
    """Persist a database activity event for service status metrics."""
    try:
        ts = _now()
        entry: Dict[str, Any] = {
            "timestamp": ts,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "operation": operation,
        }
        if detail:
            entry["detail"] = detail

        _DB_ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)

        history: List[Dict[str, Any]] = []
        if _DB_ACTIVITY_HISTORY.exists():
            try:
                history = json.loads(_DB_ACTIVITY_HISTORY.read_text())
            except Exception:
                history = []

        # Drop entries older than max age or malformed ones
        cutoff = ts - _MAX_HISTORY_SECONDS
        filtered: List[Dict[str, Any]] = []
        for item in history:
            try:
                it_ts = float(item.get("timestamp", 0))
            except Exception:
                continue
            if it_ts >= cutoff:
                filtered.append(item)
        filtered.append(entry)
        if len(filtered) > _MAX_HISTORY_ENTRIES:
            filtered = filtered[-_MAX_HISTORY_ENTRIES:]

        _DB_ACTIVITY_HISTORY.write_text(json.dumps(filtered, indent=2))
        _DB_ACTIVITY_SUMMARY.write_text(json.dumps(entry, indent=2))
    except Exception:
        # Best-effort; swallow all errors.
        pass


def load_db_activity_summary() -> Dict[str, Any]:
    """Return the latest DB activity event (may be empty)."""
    try:
        if _DB_ACTIVITY_SUMMARY.exists():
            return json.loads(_DB_ACTIVITY_SUMMARY.read_text())
    except Exception:
        return {}
    return {}


def load_db_activity_history(max_age_secs: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return recent DB activity history, optionally filtered by max_age_secs."""
    try:
        if not _DB_ACTIVITY_HISTORY.exists():
            return []
        history = json.loads(_DB_ACTIVITY_HISTORY.read_text())
        if not isinstance(history, list):
            return []
        if max_age_secs is None:
            return history
        cutoff = _now() - float(max_age_secs)
        filtered = []
        for item in history:
            try:
                ts = float(item.get("timestamp", 0))
            except Exception:
                continue
            if ts >= cutoff:
                filtered.append(item)
        return filtered
    except Exception:
        return []
