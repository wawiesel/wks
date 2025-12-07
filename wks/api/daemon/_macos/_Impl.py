"""macOS daemon implementation."""

import sys
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
            if config.daemon is None:
                raise ValueError("daemon configuration not found in config.json")
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
        return {
            "success": True,
            "type": "macos",
            "label": self.config.data.label,
            "plist_path": str(Path.home() / "Library" / "LaunchAgents" / f"{self.config.data.label}.plist"),
        }

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon macOS launchd service."""
        _uninstall_service(self.config.data)
        return {
            "success": True,
            "type": "macos",
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
                # Bootstrap also starts the service, so we're done
                return {
                    "success": True,
                    "type": "macos",
                    "label": self.config.data.label,
                    "action": "bootstrapped",
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
            return {
                "success": True,
                "type": "macos",
                "label": self.config.data.label,
                "action": "kickstarted",  # This restarts if running, starts if not
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
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{self.config.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "macos",
                "label": self.config.data.label,
            }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": e.stderr,
            }


# Entry point for running as module (e.g., python -m wks.api.daemon._macos._Impl)
if __name__ == "__main__":
    try:
        config = WKSConfig.load()
        if config.daemon is None:
            print("Error: daemon configuration not found in config.json", file=sys.stderr)
            sys.exit(1)

        daemon_impl = _Impl(config.daemon)
        daemon_impl.run()
    except KeyboardInterrupt:
        if 'daemon_impl' in locals():
            daemon_impl.stop()
        sys.exit(0)
    except Exception as e:
        print(f"Error: Daemon failed: {e}", file=sys.stderr)
        sys.exit(1)
