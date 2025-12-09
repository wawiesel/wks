"""Helper functions for daemon start command."""

from typing import TYPE_CHECKING, Any

import subprocess
import sys

if TYPE_CHECKING:
    from .Daemon import Daemon


def _start_via_service(daemon: "Daemon", backend_type: str) -> dict[str, Any]:
    """Start daemon via service manager.

    Args:
        daemon: Daemon instance
        backend_type: Backend type (for logging/debugging)

    Returns:
        Result dict with success, label, action, etc.
    """
    result = daemon.start_service()
    output = {k: v for k, v in result.items() if k != "success"}
    output["method"] = "service"
    return {
        "success": result.get("success", False),
        "output": output,
        "result_msg": (
            f"Daemon started successfully (label: {result.get('label', 'unknown')})"
            if result.get("success", False)
            else f"Error starting daemon: {result.get('error', 'unknown error')}"
        ),
    }


def _start_directly(backend_type: str) -> dict[str, Any]:
    """Start daemon directly as background process.

    Returns:
        Result dict with success, output, result_msg
    """
    python_path = sys.executable
    daemon_module = f"wks.api.daemon._{backend_type}._Impl"

    try:
        process = subprocess.Popen(
            [python_path, "-m", daemon_module],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "success": True,
            "output": {
                "type": backend_type,
                "pid": process.pid,
                "method": "direct",
            },
            "result_msg": f"Daemon started successfully (PID: {process.pid})",
        }
    except Exception as e:
        return {
            "success": False,
            "output": {"errors": [str(e)], "warnings": []},
            "result_msg": f"Error starting daemon: {e}",
        }
