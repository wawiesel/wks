"""Helper functions for daemon start command."""

import subprocess
import sys
from typing import Any

from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY


def _validate_backend_type(backend_type: str) -> tuple[bool, dict[str, Any] | None]:
    """Validate backend type is supported.

    Returns:
        (is_valid, error_output)
    """
    if backend_type not in _BACKEND_REGISTRY:
        return False, {
            "errors": [f"Unsupported backend type: {backend_type!r}"],
            "warnings": [],
            "supported": list(_BACKEND_REGISTRY.keys()),
        }
    return True, None


def _get_daemon_impl(backend_type: str, config: WKSConfig):
    """Get daemon implementation instance.

    Returns:
        Daemon implementation instance
    """
    module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
    impl_class = module._Impl
    return impl_class(config.daemon)


def _start_via_service(daemon_impl, backend_type: str) -> dict[str, Any]:
    """Start daemon via service manager.

    Returns:
        Result dict with success, label, action, etc.
    """
    result = daemon_impl.start_service()
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
