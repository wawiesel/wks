import json
from datetime import datetime

from ._get_status_path import _get_status_path


def _get_last_prune_timestamp(database_name: str) -> datetime | None:
    status_path = _get_status_path()
    if not status_path.exists():
        return None

    try:
        data = json.loads(status_path.read_text())
        if "prune_timestamps" in data:
            timestamps = data["prune_timestamps"]
            if database_name in timestamps:
                ts_str = timestamps[database_name]
                if ts_str:
                    return datetime.fromisoformat(ts_str)
    except Exception:
        pass
    return None
