"""Daemon start command - starts the daemon process."""

import subprocess
import sys

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY


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

    # Validate backend type
    backend_type = config.daemon.type
    if backend_type not in _BACKEND_REGISTRY:
        return StageResult(
            announce="Starting daemon...",
            result=f"Error: Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})",
            output={
                "success": False,
                "error": f"Unsupported backend type: {backend_type!r}",
                "supported": list(_BACKEND_REGISTRY.keys()),
            },
            success=False,
        )

    # Import and instantiate backend implementation
    try:
        module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        daemon_impl = impl_class(config.daemon)

        # Check if service is installed
        service_status = daemon_impl.get_service_status()
        if service_status.get("installed", False):
            # Start via service manager
            result = daemon_impl.start_service()
            if result.get("success", False):
                return StageResult(
                    announce="Starting daemon...",
                    result=f"Daemon started successfully (label: {result.get('label', 'unknown')})",
                    output={**result, "method": "service"},
                    success=True,
                )
            else:
                return StageResult(
                    announce="Starting daemon...",
                    result=f"Error starting daemon: {result.get('error', 'unknown error')}",
                    output=result,
                    success=False,
                )
        else:
            # Service not installed - start daemon directly in background
            python_path = sys.executable
            daemon_module = f"wks.api.daemon._{backend_type}._Impl"

            try:
                process = subprocess.Popen(
                    [python_path, "-m", daemon_module],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,  # Detach from parent process
                )
                return StageResult(
                    announce="Starting daemon...",
                    result=f"Daemon started successfully (PID: {process.pid})",
                    output={
                        "success": True,
                        "type": backend_type,
                        "pid": process.pid,
                        "method": "direct",
                    },
                    success=True,
                )
            except Exception as e:
                return StageResult(
                    announce="Starting daemon...",
                    result=f"Error starting daemon: {e}",
                    output={"success": False, "error": str(e)},
                    success=False,
                )
    except NotImplementedError as e:
        return StageResult(
            announce="Starting daemon...",
            result=f"Error: Service start not supported for backend '{backend_type}'",
            output={"success": False, "error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce="Starting daemon...",
            result=f"Error starting daemon: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )
