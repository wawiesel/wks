"""Read daemon status file contents."""

import json
from pathlib import Path
from typing import Any


def _read_daemon_file(daemon_file: Path) -> dict[str, Any]:
    """Read daemon.json file and extract warnings/errors/pid.

    Returns:
        Dict with 'warnings', 'errors', and optionally 'pid'.
        If file cannot be read or parsed, adds error to 'errors' list.
    """
    result: dict[str, Any] = {"warnings": [], "errors": []}
    if daemon_file.exists():
        try:
            daemon_data = json.loads(daemon_file.read_text())
            result["warnings"] = daemon_data.get("warnings", [])
            result["errors"] = daemon_data.get("errors", [])
            if "pid" in daemon_data:
                result["pid"] = daemon_data["pid"]
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            result["errors"].append(f"Failed to read daemon file {daemon_file}: {e}")
    return result
