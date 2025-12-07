"""Daemon uninstall command - removes daemon system service."""

from ..base import StageResult
from ..config.ConfigError import ConfigError
from ._macos._launchd import uninstall_service
from ._macos._DaemonConfigData import _DaemonConfigData


def cmd_uninstall() -> StageResult:
    """Uninstall daemon system service."""
    from ..config.WKSConfig import WKSConfig

    config = WKSConfig.load()

    if config.daemon is None:
        return StageResult(
            announce="Checking daemon configuration...",
            result="Error: daemon configuration not found in config.json",
            output={"success": False, "error": "daemon section missing from config"},
            success=False,
        )

    if config.daemon.type == "macos":
        if not isinstance(config.daemon.data, _DaemonConfigData):
            return StageResult(
                announce="Uninstalling daemon service...",
                result="Error: Invalid daemon configuration",
                output={"success": False, "error": "daemon.data structure mismatch"},
                success=False,
            )

        try:
            uninstall_service(config.daemon.data)
            return StageResult(
                announce="Uninstalling daemon service...",
                result=f"Daemon service uninstalled successfully (label: {config.daemon.data.label})",
                output={"success": True, "type": "macos", "label": config.daemon.data.label},
                success=True,
            )
        except Exception as e:
            return StageResult(
                announce="Uninstalling daemon service...",
                result=f"Error uninstalling service: {e}",
                output={"success": False, "error": str(e)},
                success=False,
            )
    else:
        return StageResult(
            announce="Uninstalling daemon service...",
            result=f"Error: Unsupported daemon type '{config.daemon.type}'",
            output={"success": False, "error": f"Unsupported type: {config.daemon.type}"},
            success=False,
        )

