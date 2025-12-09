"""Daemon status command - shows daemon status and metrics."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import DaemonStatusOutput
from .Daemon import Daemon
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
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        backend_type = config.daemon.type
        daemon_file = WKSConfig.get_home_dir() / "daemon.json"
        status_data: dict[str, Any] = {
            "running": False,
            "installed": False,
            "warnings_log": [],
            "errors_log": [],
            "log_path": str(daemon_file),
            "pid": None,
        }

        # Check service installation status via backend implementation
        yield (0.3, "Checking service status...")
        running_as_service = False
        service_pid: int | None = None
        service_data: dict[str, Any] = {}

        if backend_type in _BACKEND_REGISTRY:
            try:
                with Daemon(config.daemon) as daemon:
                    service_status = daemon.get_service_status()
                if "installed" not in service_status:
                    raise KeyError("get_service_status() result missing required 'installed' field")
                service_installed = service_status["installed"]

                # Always set installed status (True or False) for service-capable backends
                service_data["installed"] = service_installed
                if "plist_path" in service_status:
                    service_data["plist_path"] = service_status["plist_path"]
                if "label" in service_status:
                    service_data["label"] = service_status["label"]

                if service_installed and "pid" in service_status:
                    service_pid = service_status["pid"]
                    if _pid_running(service_pid):
                        running_as_service = True
                        status_data["running"] = True
                        status_data["pid"] = service_pid
                        status_data["installed"] = True
            except (NotImplementedError, Exception):
                # Backend doesn't support service status or error occurred
                pass

        # If running as service, check for warnings/errors from daemon.json
        if running_as_service:
            yield (0.7, "Reading daemon status file...")
            if daemon_file.exists():
                try:
                    import json

                    daemon_data = json.loads(daemon_file.read_text())
                    status_data["warnings_log"] = daemon_data.get("warnings", [])
                    status_data["errors_log"] = daemon_data.get("errors", [])
                except Exception:
                    pass

            yield (1.0, "Complete")
            result_obj.result = f"Daemon status retrieved (running as service, PID: {service_pid})"
            result_obj.output = DaemonStatusOutput(
                errors=[],
                warnings=[],
                running=status_data["running"],
                pid=status_data["pid"],
                installed=True,
                warnings_log=status_data["warnings_log"],
                errors_log=status_data["errors_log"],
                log_path=status_data["log_path"],
            ).model_dump(mode="python")
            result_obj.success = len(status_data["errors_log"]) == 0
            return

        # Not running as service - check for direct-run indicators
        yield (0.5, "Checking direct-run indicators...")
        terminal_pid: int | None = None
        terminal_data: dict[str, Any] = {}

        # Check lock file (created when daemon runs directly)
        lock_file = WKSConfig.get_home_dir() / "daemon.lock"
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
        if daemon_file.exists():
            try:
                import json

                daemon_data = json.loads(daemon_file.read_text())
                status_data["warnings_log"] = daemon_data.get("warnings", [])
                status_data["errors_log"] = daemon_data.get("errors", [])

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
            result_msg = f"Daemon status retrieved (running directly, PID: {terminal_pid})"
        elif service_data.get("installed") is not None:
            status_data["installed"] = service_data.get("installed", False)
            if status_data["installed"]:
                result_msg = "Daemon status retrieved (service installed but not running)"
            else:
                result_msg = "Daemon status retrieved (service not installed)"
        else:
            result_msg = "Daemon status retrieved (not running)"

        yield (1.0, "Complete")
        result_obj.result = result_msg
        result_obj.output = DaemonStatusOutput(
            errors=[],
            warnings=[],
            running=status_data["running"],
            pid=status_data["pid"],
            installed=status_data["installed"],
            warnings_log=status_data["warnings_log"],
            errors_log=status_data["errors_log"],
            log_path=status_data["log_path"],
        ).model_dump(mode="python")
        result_obj.success = len(status_data["errors_log"]) == 0

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
