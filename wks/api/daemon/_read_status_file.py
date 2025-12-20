"""Read daemon status from daemon.json (UNO: single function)."""

import json
from pathlib import Path
from typing import Any

from ..log._utils import get_logfile_path


def read_status_file(wks_home: Path) -> dict[str, Any]:
    """Read daemon.json from WKS_HOME; raises on missing/invalid."""
    log_path = str(get_logfile_path(wks_home))
    path = wks_home / "daemon.json"
    if not path.exists():
        # Missing file = clean state = not running
        return {
            "running": False,
            "pid": None,
            "restrict_dir": "",
            "log_path": log_path,
            "lock_path": str(wks_home / "daemon.lock"),
            "last_sync": None,
            "errors": [],
            "warnings": [],
        }
    try:
        content = json.loads(path.read_text())
        if not isinstance(content, dict):
            # If invalid content (e.g. not a dict), treat as empty/corrupt -> not running
            return {
                "running": False,
                "pid": None,
                "restrict_dir": "",
                "log_path": log_path,
                "lock_path": str(wks_home / "daemon.lock"),
                "last_sync": None,
                "errors": ["Corrupt daemon.json, assumed stopped"],
                "warnings": [],
            }
        return content
    except json.JSONDecodeError:
        # If empty or invalid JSON, treat as not running
        return {
            "running": False,
            "pid": None,
            "restrict_dir": "",
            "log_path": log_path,
            "lock_path": str(wks_home / "daemon.lock"),
            "last_sync": None,
            "errors": ["Invalid daemon.json, assumed stopped"],
            "warnings": [],
        }
