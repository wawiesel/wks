"""Daemon stop command - stops the daemon process."""

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY


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

    # Validate backend type
    backend_type = config.daemon.type
    if backend_type not in _BACKEND_REGISTRY:
        return StageResult(
            announce="Stopping daemon...",
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
        if not service_status.get("installed", False):
            return StageResult(
                announce="Stopping daemon...",
                result="Error: Daemon service not installed.",
                output={"success": False, "error": "service not installed"},
                success=False,
            )

        # Stop via service manager
        result = daemon_impl.stop_service()
        if result.get("success", False):
            return StageResult(
                announce="Stopping daemon...",
                result=f"Daemon stopped successfully (label: {result.get('label', 'unknown')})",
                output=result,
                success=True,
            )
        else:
            return StageResult(
                announce="Stopping daemon...",
                result=f"Error stopping daemon: {result.get('error', 'unknown error')}",
                output=result,
                success=False,
            )
    except NotImplementedError as e:
        return StageResult(
            announce="Stopping daemon...",
            result=f"Error: Service stop not supported for backend '{backend_type}'",
            output={"success": False, "error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce="Stopping daemon...",
            result=f"Error stopping daemon: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )

