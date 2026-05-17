from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

WKS_DAEMON_COMMAND_MARKERS = (
    "wks.api.daemon._child_runner",
    "wksc daemon start --blocking",
    "wks.api.daemon.cmd_start",
)


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def process_command(pid: int) -> str:
    if not pid_exists(pid):
        return ""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_wks_daemon_process(pid: int) -> bool:
    command = process_command(pid)
    if not command:
        return False
    return any(marker in command for marker in WKS_DAEMON_COMMAND_MARKERS)


def active_wks_daemon_lock(
    lock_path: Path,
    *,
    status_path: Path | None = None,
    max_status_age_seconds: float = 300.0,
) -> int | None:
    if not lock_path.exists():
        return None
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip().splitlines()[0])
    except (ValueError, IndexError, OSError):
        return None
    if pid <= 0 or not pid_exists(pid):
        return None
    if is_wks_daemon_process(pid):
        return pid
    if status_path is not None and _status_file_matches_live_daemon(
        status_path,
        pid=pid,
        max_status_age_seconds=max_status_age_seconds,
    ):
        return pid
    return None


def _status_file_matches_live_daemon(
    status_path: Path,
    *,
    pid: int,
    max_status_age_seconds: float,
) -> bool:
    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if raw.get("pid") != pid or raw.get("running") is not True:
        return False
    last_sync = raw.get("last_sync")
    if not isinstance(last_sync, str) or not last_sync:
        return False
    try:
        timestamp = dt.datetime.fromisoformat(last_sync)
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - timestamp.astimezone(dt.timezone.utc)
    return age.total_seconds() <= max_status_age_seconds
