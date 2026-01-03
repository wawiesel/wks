"""macOS service implementation - installs daemon as launchd service."""

import os
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..ServiceStatus import ServiceStatus

from ...config.WKSConfig import WKSConfig
from .._AbstractImpl import _AbstractImpl
from ..ServiceConfig import ServiceConfig
from ._Data import _Data

if TYPE_CHECKING:
    from ..ServiceStatus import ServiceStatus


class _Impl(_AbstractImpl):
    """macOS-specific service implementation."""

    @staticmethod
    def _get_launch_agents_dir() -> Path:
        """Get the LaunchAgents directory for the current user."""
        return Path.home() / "Library" / "LaunchAgents"

    @staticmethod
    def _get_plist_path(label: str) -> Path:
        """Get the plist file path for a given label."""
        return _Impl._get_launch_agents_dir() / f"{label}.plist"

    @staticmethod
    def _create_plist_content(config: _Data, wksc_path: str, restrict_dir: Path | None = None) -> str:
        """Create launchd plist XML content that runs 'wksc daemon start'.

        Args:
            config: Service configuration data
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

        # Build program arguments - run 'wksc daemon start --blocking [--restrict-dir PATH]'
        program_args = f"""    <string>{wksc_path}</string>
    <string>daemon</string>
    <string>start</string>
    <string>--blocking</string>"""
        if restrict_dir is not None:
            from ....utils.normalize_path import normalize_path

            restrict_path = str(normalize_path(restrict_dir))
            program_args += f"""
    <string>--restrict</string>
    <string>{restrict_path}</string>"""

        # Construct PATH to include wksc and potential mongod locations
        wksc_dir = Path(wksc_path).parent
        # Try to find mongod to include its path
        mongod_path = shutil.which("mongod")
        mongod_dir = Path(mongod_path).parent if mongod_path else None

        path_str = f"{wksc_dir}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        if mongod_dir and str(mongod_dir) not in path_str:
            path_str = f"{mongod_dir}:{path_str}"

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{config.label}</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>{path_str}</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>WorkingDirectory</key>
  <string>{working_directory}</string>
  <key>RunAtLoad</key>
  <{"true" if config.run_at_load else "false"}/>
  <key>KeepAlive</key>
  <{"true" if config.keep_alive else "false"}/>
  <key>StandardOutPath</key>
  <string>{log_file}</string>
  <key>StandardErrorPath</key>
  <string>{log_file}</string>
</dict>
</plist>"""
        return plist

    def __init__(self, service_config: ServiceConfig | None = None):
        """Initialize macOS service implementation.

        Args:
            service_config: Service configuration. If None, loads from WKSConfig.
        """
        if service_config is None:
            config = WKSConfig.load()
            service_config = config.service

        if not isinstance(service_config.data, _Data):
            raise ValueError("macOS service config data is required")
        self.config = service_config
        self._data: _Data = service_config.data

    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install daemon as macOS launchd service.

        The plist runs 'wksc daemon start' which handles the actual filesystem monitoring.

        Args:
            restrict_dir: Optional directory to restrict monitoring to
        """

        # Find wksc command
        wksc_path = shutil.which("wksc")
        if not wksc_path:
            raise RuntimeError("wksc command not found in PATH. Ensure WKS is installed.")

        plist_path = self._get_plist_path(self._data.label)
        plist_dir = plist_path.parent

        # Ensure LaunchAgents directory exists
        plist_dir.mkdir(parents=True, exist_ok=True)

        # Create plist content that runs 'wksc daemon start'
        plist_content = self._create_plist_content(self._data, wksc_path, restrict_dir=restrict_dir)

        # Write plist file
        plist_path.write_text(plist_content, encoding="utf-8")

        # Check if service is already loaded
        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                raise RuntimeError("Service is already installed and loaded. Use 'wksc service uninstall' first.")
        except RuntimeError:
            raise  # Re-raise our error
        except Exception:
            pass  # If check fails, proceed with bootstrap

        # Load service with launchctl
        try:
            subprocess.run(
                ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to load launchd service: {e.stderr}") from e

        return {
            "success": True,
            "type": "darwin",
            "label": self._data.label,
            "plist_path": str(plist_path),
        }

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon macOS launchd service."""
        plist_path = self._get_plist_path(self._data.label)

        if not plist_path.exists():
            return {
                "success": False,
                "type": "darwin",
                "label": self._data.label,
                "error": "Service is not installed (plist not found).",
            }

        uid = os.getuid()

        # Unload service
        with suppress(Exception):
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", str(plist_path)],
                check=False,  # Don't fail if already unloaded
                capture_output=True,
                text=True,
            )

        # Remove plist file
        if plist_path.exists():
            plist_path.unlink()

        # Remove lock file if it exists (robustness)
        from ...config.WKSConfig import WKSConfig

        lock_path = WKSConfig.get_home_dir() / "daemon.lock"
        if lock_path.exists():
            with suppress(Exception):
                lock_path.unlink()

        return {
            "success": True,
            "type": "darwin",
            "label": self._data.label,
        }

    def get_service_status(self) -> "ServiceStatus":
        """Get daemon macOS launchd service status."""
        from ..ServiceStatus import ServiceStatus

        plist_path = self._get_plist_path(self._data.label)
        uid = os.getuid()

        status = ServiceStatus(
            installed=plist_path.exists(),
            unit_path=str(plist_path),
        )

        if status.installed:
            try:
                result = subprocess.run(
                    ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    status.running = True
                    # Parse output for PID
                    for line in result.stdout.splitlines():
                        if line.strip().startswith("pid ="):
                            with suppress(ValueError, IndexError):
                                status.pid = int(line.split("=", 1)[1].strip())
            except Exception:
                pass

        return status

    def start_service(self) -> dict[str, Any]:
        """Start daemon via macOS launchctl."""
        uid = os.getuid()
        plist_path = self._get_plist_path(self._data.label)

        # First check if service is loaded
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self._data.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            service_loaded = result.returncode == 0
        except Exception:
            service_loaded = False

        # If service is not loaded but plist exists, bootstrap it first
        if not service_loaded and plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Bootstrap also starts the service, verify it's running
                import time

                time.sleep(0.5)  # Give service a moment to start
                status = self.get_service_status()
                if status.pid:
                    return {
                        "success": True,
                        "type": "darwin",
                        "label": self._data.label,
                        "action": "bootstrapped",
                        "pid": status.pid,
                    }
                else:
                    log_path = WKSConfig.get_home_dir() / "logs" / "service.log"
                    return {
                        "success": False,
                        "error": f"Service failed to start after bootstrap (no PID found). Check logs at: {log_path}",
                    }
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "error": f"Failed to bootstrap service: {e.stderr}",
                }

        # Service is loaded, use kickstart to start/restart it
        # Note: -k flag kills and restarts if already running, starts if not running
        try:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{self._data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            # Verify service actually started by checking for PID
            import time

            time.sleep(0.5)  # Give service a moment to start
            status = self.get_service_status()
            if status.pid:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self._data.label,
                    "action": "kickstarted",
                    "pid": status.pid,
                }
            else:
                # Service didn't start - check logs
                log_path = WKSConfig.get_home_dir() / "logs" / "service.log"
                return {
                    "success": False,
                    "error": f"Service failed to start (no PID found). Check logs at: {log_path}",
                }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": e.stderr,
            }

    def stop_service(self) -> dict[str, Any]:
        """Stop daemon via macOS launchctl."""
        uid = os.getuid()
        try:
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{self._data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "darwin",
                "label": self._data.label,
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            # Check for common "not running" errors - treat as success (idempotent)
            if "No such process" in error_msg or e.returncode == 3:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self._data.label,
                    "note": "Service was not running (already stopped).",
                }
            return {
                "success": False,
                "error": f"Failed to stop service: {error_msg}" if error_msg else "Failed to stop service.",
            }
