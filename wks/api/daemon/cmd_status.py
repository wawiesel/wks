"""Daemon status command - shows daemon status and metrics."""

import os
from pathlib import Path
from typing import Any

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.get_home_dir import get_home_dir
from ._macos._launchd import get_service_status
from ._macos._DaemonConfigData import _DaemonConfigData


def _pid_running(pid: int) -> bool:
    """Check if a process ID is running."""
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def cmd_status() -> StageResult:
    """Get daemon status and metrics."""
    config = WKSConfig.load()

    status_data: dict[str, Any] = {
        "daemon_configured": config.daemon is not None,
        "service_installed": False,
        "daemon_running": False,
    }

    if config.daemon is None:
        return StageResult(
            announce="Checking daemon status...",
            result="Daemon not configured (no daemon section in config.json)",
            output=status_data,
            success=True,
        )

    status_data["type"] = config.daemon.type

    # Check service installation status
    if config.daemon.type == "macos":
        if isinstance(config.daemon.data, _DaemonConfigData):
            service_status = get_service_status(config.daemon.data)
            status_data["service_installed"] = service_status.get("installed", False)
            status_data["plist_path"] = service_status.get("plist_path")

            if "pid" in service_status:
                pid = service_status["pid"]
                status_data["pid"] = pid
                status_data["daemon_running"] = _pid_running(pid)

    # Check lock file
    lock_file = get_home_dir("daemon.lock")
    status_data["lock_file_exists"] = lock_file.exists()
    if lock_file.exists():
        try:
            lock_content = lock_file.read_text().strip()
            if lock_content:
                try:
                    lock_pid = int(lock_content.splitlines()[0])
                    status_data["lock_pid"] = lock_pid
                    status_data["daemon_running"] = _pid_running(lock_pid)
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

    # Check daemon status file
    daemon_file = get_home_dir("daemon.json")
    status_data["daemon_file_exists"] = daemon_file.exists()
    if daemon_file.exists():
        try:
            import json

            daemon_data = json.loads(daemon_file.read_text())
            status_data["daemon"] = daemon_data
            if "pid" in daemon_data:
                status_data["daemon_running"] = _pid_running(daemon_data["pid"])
        except Exception:
            pass

    result_msg = "Daemon status retrieved"
    if status_data["daemon_running"]:
        result_msg += f" (running, PID: {status_data.get('pid', status_data.get('lock_pid', 'unknown'))})"
    elif status_data["service_installed"]:
        result_msg += " (service installed but not running)"
    else:
        result_msg += " (not installed)"

    return StageResult(
        announce="Checking daemon status...",
        result=result_msg,
        output=status_data,
        success=True,
    )

