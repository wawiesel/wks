import subprocess
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...config.WKSConfig import WKSConfig
from .._AbstractImpl import _AbstractImpl
from .._shared import prepare_service_home, remove_daemon_lock, resolve_wksc_path
from ..ServiceConfig import ServiceConfig
from ._Data import _Data

if TYPE_CHECKING:
    from ..ServiceStatus import ServiceStatus


class _Impl(_AbstractImpl):
    @staticmethod
    def _get_systemd_user_dir() -> Path:
        return Path.home() / ".config" / "systemd" / "user"

    @staticmethod
    def _get_unit_path(unit_name: str) -> Path:
        return _Impl._get_systemd_user_dir() / unit_name

    @staticmethod
    def _create_unit_content(_config: _Data, wksc_path: str, restrict_dir: Path | None = None) -> str:
        working_directory, log_file = prepare_service_home()

        exec_start = f"{wksc_path} daemon start --blocking"
        if restrict_dir is not None:
            from ....utils.normalize_path import normalize_path

            restrict_path = str(normalize_path(restrict_dir))
            exec_start += f" --restrict {restrict_path}"

        unit = f"""[Unit]
Description=WKS Daemon Service
After=network.target

[Service]
Type=simple
Environment=WKS_HOME={working_directory}
ExecStart={exec_start}
PIDFile={working_directory}/daemon.lock
WorkingDirectory={working_directory}
StandardOutput=append:{log_file}
StandardError=append:{log_file}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""
        return unit

    def __init__(self, service_config: ServiceConfig | None = None):
        if service_config is None:
            config = WKSConfig.load()
            service_config = config.service

        if not isinstance(service_config.data, _Data):
            raise ValueError("Linux service config data is required")
        self.config = service_config
        self._data: _Data = service_config.data

    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        wksc_path = resolve_wksc_path()

        unit_path = self._get_unit_path(self._data.unit_name)
        unit_dir = unit_path.parent

        unit_dir.mkdir(parents=True, exist_ok=True)

        unit_content = self._create_unit_content(self._data, wksc_path, restrict_dir=restrict_dir)

        unit_path.write_text(unit_content, encoding="utf-8")

        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to reload systemd daemon: {e.stderr}") from e

        if self._data.enabled:
            try:
                subprocess.run(
                    ["systemctl", "--user", "enable", self._data.unit_name],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to enable service: {e.stderr}") from e

        return {
            "success": True,
            "type": "linux",
            "unit_name": self._data.unit_name,
            "unit_path": str(unit_path),
        }

    def uninstall_service(self) -> dict[str, Any]:
        unit_path = self._get_unit_path(self._data.unit_name)

        if not unit_path.exists():
            return {
                "success": False,
                "type": "linux",
                "unit_name": self._data.unit_name,
                "error": "Service is not installed (unit file not found).",
            }

        with suppress(Exception):
            subprocess.run(
                ["systemctl", "--user", "stop", self._data.unit_name],
                check=False,
                capture_output=True,
                text=True,
            )
        with suppress(Exception):
            subprocess.run(
                ["systemctl", "--user", "disable", self._data.unit_name],
                check=False,
                capture_output=True,
                text=True,
            )

        if unit_path.exists():
            unit_path.unlink()

        remove_daemon_lock()

        with suppress(Exception):
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=False,
                capture_output=True,
                text=True,
            )

        return {
            "success": True,
            "type": "linux",
            "unit_name": self._data.unit_name,
        }

    def get_service_status(self) -> "ServiceStatus":
        from ..ServiceStatus import ServiceStatus

        unit_path = self._get_unit_path(self._data.unit_name)

        status = ServiceStatus(
            installed=unit_path.exists(),
            unit_path=str(unit_path),
        )

        if status.installed:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", self._data.unit_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                status.running = result.returncode == 0

                if status.running:
                    pid_result = subprocess.run(
                        ["systemctl", "--user", "show", self._data.unit_name, "--property=MainPID", "--value"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if pid_result.returncode == 0:
                        pid_str = pid_result.stdout.strip()
                        if pid_str and pid_str != "0":
                            with suppress(ValueError):
                                status.pid = int(pid_str)
            except Exception:
                pass

        return status

    def start_service(self) -> dict[str, Any]:
        unit_path = self._get_unit_path(self._data.unit_name)

        if not unit_path.exists():
            return {
                "success": False,
                "error": f"Service unit file not found at {unit_path}. Install the service first.",
            }

        try:
            subprocess.run(
                ["systemctl", "--user", "start", self._data.unit_name],
                check=True,
                capture_output=True,
                text=True,
            )
            import time

            time.sleep(0.5)  # Give service a moment to start
            status = self.get_service_status()
            if status.running:
                return {
                    "success": True,
                    "type": "linux",
                    "unit_name": self._data.unit_name,
                    "pid": status.pid,
                }
            else:
                log_path = WKSConfig.get_home_dir() / "logs" / "service.log"
                return {
                    "success": False,
                    "error": f"Service failed to start. Check logs at: {log_path}",
                }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            return {
                "success": False,
                "error": f"Failed to start service: {error_msg}",
            }

    def stop_service(self) -> dict[str, Any]:
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", self._data.unit_name],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "linux",
                "unit_name": self._data.unit_name,
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            if "not loaded" in error_msg.lower() or "not found" in error_msg.lower():
                return {
                    "success": True,
                    "type": "linux",
                    "unit_name": self._data.unit_name,
                    "note": "Service was not running (already stopped).",
                }
            return {
                "success": False,
                "error": f"Failed to stop service: {error_msg}" if error_msg else "Failed to stop service.",
            }
