import contextlib
import json
from datetime import datetime, timezone

from ._get_status_path import _get_status_path


def _set_last_prune_timestamp(database_name: str, timestamp: datetime | None = None) -> None:
    status_path = _get_status_path()

    data: dict = {}
    if status_path.exists():
        with contextlib.suppress(Exception):
            data = json.loads(status_path.read_text())

    if "prune_timestamps" not in data:
        data["prune_timestamps"] = {}

    ts = timestamp or datetime.now(timezone.utc)
    data["prune_timestamps"][database_name] = ts.isoformat()

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(data, indent=2))
