"""macOS daemon implementation."""

from pathlib import Path
from typing import Any

from .._AbstractImpl import _AbstractImpl
from ..DaemonConfig import DaemonConfig
from ...config.WKSConfig import WKSConfig
from ._DaemonConfigData import _DaemonConfigData
from ._launchd import install_service as _install_service, uninstall_service as _uninstall_service, get_service_status as _get_service_status


class _Impl(_AbstractImpl):
    """macOS-specific daemon implementation."""

    def __init__(self, daemon_config: DaemonConfig | None = None):
        """Initialize macOS daemon implementation.

        Args:
            daemon_config: Daemon configuration. If None, loads from WKSConfig.
        """
        if daemon_config is None:
            config = WKSConfig.load()
            daemon_config = config.daemon

        if not isinstance(daemon_config.data, _DaemonConfigData):
            raise ValueError("macOS daemon config data is required")
        self.config = daemon_config
        self._running = False

    def run(self) -> None:
        """Run the daemon main loop.

        TODO: Implement daemon functionality:
        - Monitor filesystem and update monitor database
        - Maintain vault links and sync with Obsidian
        - Provide MCP broker for AI agent access
        - Write status to daemon.json
        """
        self._running = True
        # TODO: Implement actual daemon logic
        # For now, this is a placeholder
        import time
        while self._running:
            time.sleep(1)

    def stop(self) -> None:
        """Stop the daemon gracefully."""
        self._running = False

    def install_service(self, python_path: str, project_root: Path) -> dict[str, Any]:
        """Install daemon as macOS launchd service."""
        module_path = f"wks.api.daemon._{self.config.type}._Impl"
        _install_service(self.config.data, python_path, module_path, project_root)
        plist_path = str(Path.home() / "Library" / "LaunchAgents" / f"{self.config.data.label}.plist")

        return {
            "success": True,
            "type": "darwin",
            "label": self.config.data.label,
            "plist_path": plist_path,
        }

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon macOS launchd service."""
        _uninstall_service(self.config.data)
        return {
            "success": True,
            "type": "darwin",
            "label": self.config.data.label,
        }

    def get_service_status(self) -> dict[str, Any]:
        """Get daemon macOS launchd service status."""
        return _get_service_status(self.config.data)

    def start_service(self) -> dict[str, Any]:
        """Start daemon via macOS launchctl."""
        import os
        import subprocess
        from pathlib import Path

        from ._launchd import _get_plist_path

        uid = os.getuid()
        plist_path = _get_plist_path(self.config.data.label)

        # First check if service is loaded
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self.config.data.label}"],
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
                status = _get_service_status(self.config.data)
                if "pid" in status:
                    return {
                        "success": True,
                        "type": "darwin",
                        "label": self.config.data.label,
                        "action": "bootstrapped",
                        "pid": status["pid"],
                    }
                else:
                    log_path = Path(self.config.data.log_file).expanduser()
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
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.config.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            # Verify service actually started by checking for PID
            import time
            time.sleep(0.5)  # Give service a moment to start
            status = _get_service_status(self.config.data)
            if "pid" in status:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self.config.data.label,
                    "action": "kickstarted",
                    "pid": status["pid"],
                }
            else:
                # Service didn't start - check logs
                log_path = Path(self.config.data.log_file).expanduser()
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
        import os
        import subprocess

        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{self.config.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "darwin",
                "label": self.config.data.label,
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            # Check for common "not running" errors - treat as success (idempotent)
            if "No such process" in error_msg or e.returncode == 3:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self.config.data.label,
                    "note": "Service was not running (already stopped).",
                }
            return {
                "success": False,
                "error": f"Failed to stop service: {error_msg}" if error_msg else "Failed to stop service.",
            }
