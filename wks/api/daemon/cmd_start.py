"""Daemon start command - starts the daemon process."""

import subprocess
import sys

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from ._macos._launchd import get_service_status
from ._macos._DaemonConfigData import _DaemonConfigData


def cmd_start() -> StageResult:
    """Start daemon process."""
    config = WKSConfig.load()

    if config.daemon is None:
        return StageResult(
            announce="Starting daemon...",
            result="Error: daemon configuration not found in config.json",
            output={"success": False, "error": "daemon section missing from config"},
            success=False,
        )

    if config.daemon.type == "macos":
        if not isinstance(config.daemon.data, _DaemonConfigData):
            return StageResult(
                announce="Starting daemon...",
                result="Error: Invalid daemon configuration",
                output={"success": False, "error": "daemon.data structure mismatch"},
                success=False,
            )

        # Check if service is installed
        service_status = get_service_status(config.daemon.data)
        if not service_status.get("installed", False):
            return StageResult(
                announce="Starting daemon...",
                result="Error: Daemon service not installed. Run 'wksc daemon install' first.",
                output={"success": False, "error": "service not installed"},
                success=False,
            )

        # Start via launchctl
        import os

        uid = os.getuid()
        try:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{config.daemon.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return StageResult(
                announce="Starting daemon...",
                result=f"Daemon started successfully (label: {config.daemon.data.label})",
                output={"success": True, "type": "macos", "label": config.daemon.data.label},
                success=True,
            )
        except subprocess.CalledProcessError as e:
            return StageResult(
                announce="Starting daemon...",
                result=f"Error starting daemon: {e.stderr}",
                output={"success": False, "error": e.stderr},
                success=False,
            )
    else:
        return StageResult(
            announce="Starting daemon...",
            result=f"Error: Unsupported daemon type '{config.daemon.type}'",
            output={"success": False, "error": f"Unsupported type: {config.daemon.type}"},
            success=False,
        )

