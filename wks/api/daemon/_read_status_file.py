"""Read daemon status from daemon.json (UNO: single function)."""

import json
from pathlib import Path
from typing import Any


def read_status_file(wks_home: Path) -> dict[str, Any]:
    """Read daemon.json from WKS_HOME; raises on missing/invalid."""
    path = wks_home / "daemon.json"
    if not path.exists():
        raise FileNotFoundError(f"daemon.json not found at {path}")
    content = json.loads(path.read_text())
    if not isinstance(content, dict):
        raise ValueError("daemon.json content must be an object")
    return content
