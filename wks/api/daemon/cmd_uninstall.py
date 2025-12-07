"""Daemon uninstall command - removes daemon system service."""

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY


def cmd_uninstall() -> StageResult:
    """Uninstall daemon system service."""
    config = WKSConfig.load()

    if config.daemon is None:
        return StageResult(
            announce="Checking daemon configuration...",
            result="Error: daemon configuration not found in config.json",
            output={"success": False, "error": "daemon section missing from config"},
            success=False,
        )

    # Validate backend type
    backend_type = config.daemon.type
    if backend_type not in _BACKEND_REGISTRY:
        return StageResult(
            announce="Uninstalling daemon service...",
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

        # Uninstall via backend implementation
        result = daemon_impl.uninstall_service()

        return StageResult(
            announce="Uninstalling daemon service...",
            result=f"Daemon service uninstalled successfully (label: {result.get('label', 'unknown')})",
            output=result,
            success=result.get("success", True),
        )
    except NotImplementedError as e:
        return StageResult(
            announce="Uninstalling daemon service...",
            result=f"Error: Service uninstallation not supported for backend '{backend_type}'",
            output={"success": False, "error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce="Uninstalling daemon service...",
            result=f"Error uninstalling service: {e}",
            output={"success": False, "error": str(e)},
            success=False,
        )

