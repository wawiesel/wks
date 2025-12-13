"""Linux service implementation - installs daemon as systemd user service."""

import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import Any

from ...config.WKSConfig import WKSConfig
from .._AbstractImpl import _AbstractImpl
from ..ServiceConfig import ServiceConfig
from ._Data import _Data


class _Impl(_AbstractImpl):
    """Linux-specific service implementation using systemd user services."""

    @staticmethod
    def _get_systemd_user_dir() -> Path:
        """Get the systemd user directory for the current user."""
        return Path.home() / ".config" / "systemd" / "user"

    @staticmethod
    def _get_unit_path(unit_name: str) -> Path:
        """Get the systemd unit file path for a given unit name."""
        return _Impl._get_systemd_user_dir() / unit_name

    @staticmethod
    def _create_unit_content(_config: _Data, wksc_path: str, restrict_dir: Path | None = None) -> str:
        """Create systemd unit file content that runs 'wksc daemon start'.

        Args:
            _config: Service configuration data (unused in Linux implementation, kept for API consistency)
            wksc_path: Path to wksc CLI command
            restrict_dir: Optional directory to restrict monitoring to
        """
        # Working directory is always WKS_HOME
        working_directory = WKSConfig.get_home_dir()

        # Single standardized log file under WKS_HOME
        log_file = working_directory / "logs" / "service.log"

        # Ensure directories exist
        log_file.parent.mkdir(parents=True, exist_ok=True)
        working_directory.mkdir(parents=True, exist_ok=True)

        # Build ExecStart command - run 'wksc daemon start [--restrict-dir PATH]'
        exec_start = f"{wksc_path} daemon start"
        if restrict_dir is not None:
            restrict_path = str(restrict_dir.expanduser().resolve())
            exec_start += f" --restrict-dir {restrict_path}"

        unit = f"""[Unit]
Description=WKS Daemon Service
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
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
        """Initialize Linux service implementation.

        Args:
            service_config: Service configuration. If None, loads from WKSConfig.
        """
        if service_config is None:
            config = WKSConfig.load()
            service_config = config.service

        if not isinstance(service_config.data, _Data):
            raise ValueError("Linux service config data is required")
        self.config = service_config
        self._data: _Data = service_config.data

    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install daemon as Linux systemd user service.

        The unit file runs 'wksc daemon start' which handles the actual filesystem monitoring.

        Args:
            restrict_dir: Optional directory to restrict monitoring to
        """
        # Find wksc command
        wksc_path = shutil.which("wksc")
        if not wksc_path:
            raise RuntimeError("wksc command not found in PATH. Ensure WKS is installed.")

        unit_path = self._get_unit_path(self._data.unit_name)
        unit_dir = unit_path.parent

        # Ensure systemd user directory exists
        unit_dir.mkdir(parents=True, exist_ok=True)

        # Create unit file content that runs 'wksc daemon start'
        unit_content = self._create_unit_content(self._data, wksc_path, restrict_dir=restrict_dir)

        # Write unit file
        unit_path.write_text(unit_content, encoding="utf-8")

        # Reload systemd daemon to pick up new unit
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to reload systemd daemon: {e.stderr}") from e

        # Enable service if requested
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
        """Uninstall daemon Linux systemd user service."""
        unit_path = self._get_unit_path(self._data.unit_name)

        # Stop and disable service
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

        # Remove unit file
        if unit_path.exists():
            unit_path.unlink()

        # Reload systemd daemon
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

    def get_service_status(self) -> dict[str, Any]:
        """Get daemon Linux systemd user service status."""
        unit_path = self._get_unit_path(self._data.unit_name)

        status: dict[str, Any] = {
            "installed": unit_path.exists(),
            "unit_path": str(unit_path),
        }

        if status["installed"]:
            try:
                # Check if service is active
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", self._data.unit_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                status["running"] = result.returncode == 0

                # Get PID if running
                if status["running"]:
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
                                status["pid"] = int(pid_str)
            except Exception:
                pass

        return status

    def start_service(self) -> dict[str, Any]:
        """Start daemon via Linux systemctl."""
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
            # Verify service actually started by checking status
            import time

            time.sleep(0.5)  # Give service a moment to start
            status = self.get_service_status()
            if status.get("running"):
                return {
                    "success": True,
                    "type": "linux",
                    "unit_name": self._data.unit_name,
                    "pid": status.get("pid"),
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
        """Stop daemon via Linux systemctl."""
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
            # Check for common "not running" errors - treat as success (idempotent)
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
