from collections.abc import Iterator
from typing import Any

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..daemon.process_identity import active_wks_daemon_lock
from . import ServiceStatusOutput
from ._pid_running import _pid_running
from ._read_daemon_file import _read_daemon_file
from .Service import Service

"""Service status command - shows service-managed daemon status and metrics."""


def cmd_status() -> StageResult:
    def _check_service_status(
        config: WKSConfig, status_data: dict[str, Any]
    ) -> tuple[bool, int | None, dict[str, Any]]:
        running_as_service = False
        service_pid: int | None = None
        service_data: dict[str, Any] = {}

        try:
            with Service(config.service) as service:
                service_status = service.get_service_status()

            service_data["installed"] = service_status.installed
            if service_status.unit_path:
                service_data["plist_path"] = service_status.unit_path

            if service_status.installed and service_status.pid:
                service_pid = service_status.pid
                if _pid_running(service_pid):
                    running_as_service = True
                    status_data["running"] = True
                    status_data["pid"] = service_pid
        except ValueError as exc:
            status_data["warnings"].append(f"Service backend not supported: {exc}")
        except NotImplementedError as exc:
            status_data["warnings"].append(str(exc))
        except Exception as exc:
            status_data["errors"].append(f"service status error: {exc}")

        return running_as_service, service_pid, service_data

    def _check_direct_run_indicators(status_data: dict[str, Any]) -> int | None:
        terminal_pid: int | None = None
        daemon_file = WKSConfig.get_home_dir() / "daemon.json"

        lock_file = WKSConfig.get_home_dir() / "daemon.lock"
        terminal_pid = active_wks_daemon_lock(lock_file, status_path=daemon_file)

        try:
            daemon_file_data = _read_daemon_file(daemon_file)
            status_data["warnings"] = daemon_file_data["warnings"]
            status_data["errors"] = daemon_file_data["errors"]
        except Exception as exc:
            status_data["errors"].append(f"daemon status read error: {exc}")

        return terminal_pid

    def _build_result_message(
        terminal_pid: int | None, service_data: dict[str, Any], status_data: dict[str, Any]
    ) -> str:
        if terminal_pid:
            return f"Daemon status retrieved (running directly, PID: {terminal_pid})"
        if "installed" in service_data:
            status_data["installed"] = service_data["installed"]
            if status_data["installed"]:
                return "Daemon status retrieved (service installed but not running)"
            return "Daemon status retrieved (service not installed)"
        return "Daemon status retrieved (not running)"

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        daemon_file = WKSConfig.get_home_dir() / "daemon.json"
        status_data: dict[str, Any] = {
            "running": False,
            "installed": False,
            "warnings": [],
            "errors": [],
            "log_path": str(WKSConfig.get_logfile_path()),
            "pid": None,
        }

        yield (0.3, "Checking service status...")
        running_as_service, service_pid, service_data = _check_service_status(config, status_data)

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
            result_obj.success = True
            return

        yield (0.5, "Checking direct-run indicators...")
        terminal_pid = _check_direct_run_indicators(status_data)

        if terminal_pid:
            status_data["running"] = True
            status_data["pid"] = terminal_pid

        result_msg = _build_result_message(terminal_pid, service_data, status_data)

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
        result_obj.success = True

    return StageResult(
        announce="Checking daemon status...",
        progress_callback=do_work,
    )
