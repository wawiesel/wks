"""Read daemon status file contents."""

import json
from pathlib import Path
from typing import Any


def read_daemon_file(daemon_file: Path) -> dict[str, Any]:
    """Read daemon.json file and extract warnings/errors/pid."""
    result: dict[str, Any] = {"warnings": [], "errors": []}
    if daemon_file.exists():
        try:
            daemon_data = json.loads(daemon_file.read_text())
            result["warnings"] = daemon_data.get("warnings", [])
            result["errors"] = daemon_data.get("errors", [])
            if "pid" in daemon_data:
                result["pid"] = daemon_data["pid"]
        except Exception:
            pass
    return result
