"""Daemon install command - installs daemon as system service."""

import sys
from pathlib import Path

from ..base import StageResult
from ..config.ConfigError import ConfigError
from ._detect_os import detect_os
from ._macos._launchd import install_service
from ._macos._DaemonConfigData import _DaemonConfigData


def cmd_install() -> StageResult:
    """Install daemon as system service.

    Reads daemon configuration from config.json, validates type matches OS,
    and installs appropriate service mechanism.
    """
    from ..config.WKSConfig import WKSConfig

    config = WKSConfig.load()

    # Check daemon config exists
    if config.daemon is None:
        return StageResult(
            announce="Checking daemon configuration...",
            result="Error: daemon configuration not found in config.json",
            output={"success": False, "error": "daemon section missing from config"},
            success=False,
        )

    # Detect OS
    try:
        detected_os = detect_os()
    except RuntimeError as e:
        return StageResult(
            announce="Detecting operating system...",
            result=f"Error: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )

    # Validate type matches OS
    if config.daemon.type != detected_os:
        return StageResult(
            announce="Validating daemon configuration...",
            result=f"Error: daemon.type '{config.daemon.type}' does not match detected OS '{detected_os}'",
            output={
                "success": False,
                "error": f"daemon.type mismatch: expected '{detected_os}', got '{config.daemon.type}'",
                "detected_os": detected_os,
                "configured_type": config.daemon.type,
            },
            success=False,
        )

    # Validate data structure matches type
    if not isinstance(config.daemon.data, _DaemonConfigData):
        return StageResult(
            announce="Validating daemon configuration...",
            result=f"Error: daemon.data structure does not match daemon.type '{config.daemon.type}'",
            output={
                "success": False,
                "error": "daemon.data structure mismatch",
                "type": config.daemon.type,
            },
            success=False,
        )

    # Install based on type
    if config.daemon.type == "macos":
        try:
            # Get Python path and module
            python_path = sys.executable
            module_path = "wks.daemon"  # TODO: This will be the daemon module when implemented
            # Use project root (where wks package is located) for PYTHONPATH
            import wks
            project_root = Path(wks.__file__).parent.parent

            install_service(config.daemon.data, python_path, module_path, project_root)

            return StageResult(
                announce="Installing daemon service...",
                result=f"Daemon service installed successfully (label: {config.daemon.data.label})",
                output={
                    "success": True,
                    "type": "macos",
                    "label": config.daemon.data.label,
                    "plist_path": str(Path.home() / "Library" / "LaunchAgents" / f"{config.daemon.data.label}.plist"),
                },
                success=True,
            )
        except Exception as e:
            return StageResult(
                announce="Installing daemon service...",
                result=f"Error installing service: {e}",
                output={"success": False, "error": str(e)},
                success=False,
            )
    else:
        return StageResult(
            announce="Installing daemon service...",
            result=f"Error: Unsupported daemon type '{config.daemon.type}'",
            output={"success": False, "error": f"Unsupported type: {config.daemon.type}"},
            success=False,
        )

