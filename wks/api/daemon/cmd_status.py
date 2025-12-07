"""Daemon status command - shows daemon status and metrics."""

import os
from pathlib import Path
from typing import Any

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from ..config.get_home_dir import get_home_dir
from .DaemonConfig import _BACKEND_REGISTRY


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

    if config.daemon is None:
        return StageResult(
            announce="Checking daemon status...",
            result="Daemon not configured (no daemon section in config.json)",
            output={
                "running": False,
                "type": None,
                "warnings": [],
                "errors": [],
                "data": {},
            },
            success=True,
        )

    backend_type = config.daemon.type
    status_data: dict[str, Any] = {
        "running": False,
        "type": None,
        "warnings": [],
        "errors": [],
        "data": {},
    }

    # Check service installation status via backend implementation
    running_as_service = False
    service_pid: int | None = None
    service_data: dict[str, Any] = {}

    if backend_type in _BACKEND_REGISTRY:
        try:
            module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
            impl_class = module._Impl
            daemon_impl = impl_class(config.daemon)
            service_status = daemon_impl.get_service_status()
            service_installed = service_status.get("installed", False)

            # Always set installed status (True or False) for service-capable backends
            service_data["installed"] = service_installed
            if "plist_path" in service_status:
                service_data["plist_path"] = service_status.get("plist_path")
            if "label" in service_status:
                service_data["label"] = service_status.get("label")

            if service_installed and "pid" in service_status:
                service_pid = service_status["pid"]
                if _pid_running(service_pid):
                    running_as_service = True
                    status_data["running"] = True
                    status_data["pid"] = service_pid
                    status_data["type"] = "service"
                    status_data["data"] = service_data
        except (NotImplementedError, Exception):
            # Backend doesn't support service status or error occurred
            pass

    # If running as service, check for warnings/errors from daemon.json
    if running_as_service:
        daemon_file = get_home_dir("daemon.json")
        if daemon_file.exists():
            try:
                import json

                daemon_data = json.loads(daemon_file.read_text())
                status_data["warnings"] = daemon_data.get("warnings", [])
                status_data["errors"] = daemon_data.get("errors", [])
            except Exception:
                pass

        result_msg = f"Daemon status retrieved (running as service, PID: {service_pid})"
        return StageResult(
            announce="Checking daemon status...",
            result=result_msg,
            output=status_data,
            success=True,
        )

    # Not running as service - check for direct-run indicators
    terminal_pid: int | None = None
    terminal_data: dict[str, Any] = {}

    # Check lock file (created when daemon runs directly)
    lock_file = get_home_dir("daemon.lock")
    if lock_file.exists():
        try:
            lock_content = lock_file.read_text().strip()
            if lock_content:
                try:
                    lock_pid = int(lock_content.splitlines()[0])
                    if _pid_running(lock_pid):
                        terminal_pid = lock_pid
                        terminal_data["lock_file"] = str(lock_file)
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

    # Check daemon status file (written by daemon when running directly)
    daemon_file = get_home_dir("daemon.json")
    if daemon_file.exists():
        try:
            import json

            daemon_data = json.loads(daemon_file.read_text())
            status_data["warnings"] = daemon_data.get("warnings", [])
            status_data["errors"] = daemon_data.get("errors", [])

            if "pid" in daemon_data:
                daemon_pid = daemon_data["pid"]
                if _pid_running(daemon_pid):
                    terminal_pid = daemon_pid
        except Exception:
            pass

    # If we found a running process via direct mode
    if terminal_pid:
        status_data["running"] = True
        status_data["pid"] = terminal_pid
        status_data["type"] = "terminal"
        status_data["data"] = terminal_data

        result_msg = f"Daemon status retrieved (running directly, PID: {terminal_pid})"
    elif service_data.get("installed") is not None:
        # Service-capable backend: show service status even if not installed
        status_data["type"] = "service"
        status_data["data"] = service_data
        if service_data.get("installed", False):
            result_msg = "Daemon status retrieved (service installed but not running)"
        else:
            result_msg = "Daemon status retrieved (service not installed)"
    else:
        result_msg = "Daemon status retrieved (not running)"

    return StageResult(
        announce="Checking daemon status...",
        result=result_msg,
        output=status_data,
        success=True,
    )

