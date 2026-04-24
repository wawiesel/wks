import json
from pathlib import Path
from typing import Any

from ..log.summarize_status_log_messages import summarize_status_log_messages


def _read_daemon_file(daemon_file: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"warnings": [], "errors": []}
    if daemon_file.exists():
        try:
            daemon_data = json.loads(daemon_file.read_text())
            if "warnings" in daemon_data:
                result["warnings"] = daemon_data["warnings"]
            if "errors" in daemon_data:
                result["errors"] = daemon_data["errors"]
            result["warnings"], result["errors"] = summarize_status_log_messages(
                result["warnings"],
                result["errors"],
            )
            if "pid" in daemon_data:
                result["pid"] = daemon_data["pid"]
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            result["errors"].append(f"Failed to read daemon file {daemon_file}: {e}")
    return result
