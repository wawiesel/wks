"""Service status command - shows service-managed daemon status and metrics."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import ServiceStatusOutput
from .Service import Service
from ._pid_running import _pid_running
from ._read_daemon_file import _read_daemon_file


def cmd_status() -> StageResult:
    """Get daemon status and metrics."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        daemon_file = WKSConfig.get_home_dir() / "daemon.json"
        status_data: dict[str, Any] = {
            "running": False,
            "installed": False,
            "warnings": [],
            "errors": [],
            "log_path": str(daemon_file),
            "pid": None,
        }

        # Check service installation status via backend implementation
        yield (0.3, "Checking service status...")
        running_as_service = False
        service_pid: int | None = None
        service_data: dict[str, Any] = {}

        try:
            with Service(config.service) as service:
                service_status = service.get_service_status()
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
        except ValueError as exc:
            # Unsupported backend type - not an error, just no service support
            status_data["warnings"].append(f"Service backend not supported: {exc}")
        except NotImplementedError as exc:
            status_data["warnings"].append(str(exc))
        except Exception as exc:
            status_data["errors"].append(f"service status error: {exc}")

        # If running as service, check for warnings/errors from daemon.json
        if running_as_service:
            yield (0.7, "Reading daemon status file...")
            daemon_file_data = _read_daemon_file(daemon_file)
            status_data["warnings"] = daemon_file_data["warnings"]
            status_data["errors"] = daemon_file_data["errors"]

            yield (1.0, "Complete")
            result_obj.result = f"Daemon status retrieved (running as service, PID: {service_pid})"
            result_obj.output = ServiceStatusOutput(
                errors=status_data["errors"],
                warnings=status_data["warnings"],
                running=status_data["running"],
                pid=status_data["pid"],
                installed=True,
                log_path=status_data["log_path"],
            ).model_dump(mode="python")
            result_obj.success = len(status_data["errors"]) == 0
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
                    except (ValueError, IndexError) as exc:
                        status_data["warnings"].append(f"Invalid lock file content: {exc}")
            except Exception as exc:
                status_data["warnings"].append(f"Unable to read lock file: {exc}")

        # Check daemon status file (written by daemon when running directly)
        try:
            daemon_file_data = _read_daemon_file(daemon_file)
            status_data["warnings"] = daemon_file_data["warnings"]
            status_data["errors"] = daemon_file_data["errors"]
            if "pid" in daemon_file_data:
                daemon_pid = daemon_file_data["pid"]
                if _pid_running(daemon_pid):
                    terminal_pid = daemon_pid
        except Exception as exc:
            status_data["errors"].append(f"daemon status read error: {exc}")

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
        result_obj.output = ServiceStatusOutput(
            errors=status_data["errors"],
            warnings=status_data["warnings"],
            running=status_data["running"],
            pid=status_data["pid"],
            installed=status_data["installed"],
            log_path=status_data["log_path"],
        ).model_dump(mode="python")
        result_obj.success = len(status_data["errors"]) == 0

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
