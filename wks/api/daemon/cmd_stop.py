"""Daemon stop command - stops the daemon process."""

import subprocess

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from ._macos._launchd import get_service_status
from ._macos._DaemonConfigData import _DaemonConfigData


def cmd_stop() -> StageResult:
    """Stop daemon process."""
    config = WKSConfig.load()

    if config.daemon is None:
        return StageResult(
            announce="Stopping daemon...",
            result="Error: daemon configuration not found in config.json",
            output={"success": False, "error": "daemon section missing from config"},
            success=False,
        )

    if config.daemon.type == "macos":
        if not isinstance(config.daemon.data, _DaemonConfigData):
            return StageResult(
                announce="Stopping daemon...",
                result="Error: Invalid daemon configuration",
                output={"success": False, "error": "daemon.data structure mismatch"},
                success=False,
            )

        # Check if service is installed
        service_status = get_service_status(config.daemon.data)
        if not service_status.get("installed", False):
            return StageResult(
                announce="Stopping daemon...",
                result="Error: Daemon service not installed.",
                output={"success": False, "error": "service not installed"},
                success=False,
            )

        # Stop via launchctl
        import os

        uid = os.getuid()
        try:
            # Unload the service (stops it)
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{config.daemon.data.label}"],
                check=False,  # Don't fail if already stopped
                capture_output=True,
                text=True,
            )
            return StageResult(
                announce="Stopping daemon...",
                result=f"Daemon stopped successfully (label: {config.daemon.data.label})",
                output={"success": True, "type": "macos", "label": config.daemon.data.label},
                success=True,
            )
        except Exception as e:
            return StageResult(
                announce="Stopping daemon...",
                result=f"Error stopping daemon: {e}",
                output={"success": False, "error": str(e)},
                success=False,
            )
    else:
        return StageResult(
            announce="Stopping daemon...",
            result=f"Error: Unsupported daemon type '{config.daemon.type}'",
            output={"success": False, "error": f"Unsupported type: {config.daemon.type}"},
            success=False,
        )

