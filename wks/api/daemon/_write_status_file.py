"""Write daemon status to daemon.json (UNO: single function)."""

import json
from pathlib import Path
from typing import Any


def write_status_file(status: dict[str, Any], *, wks_home: Path) -> None:
    """Write daemon status to {WKS_HOME}/daemon.json."""
    path = wks_home / "daemon.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    tmp.replace(path)
