"""Daemon install command - installs daemon as system service."""

import sys
from pathlib import Path

from ..base import StageResult
from ..config.WKSConfig import WKSConfig
from .DaemonConfig import _BACKEND_REGISTRY


def cmd_install() -> StageResult:
    """Install daemon as system service.

    Reads daemon configuration from config.json and installs appropriate service mechanism
    using the backend implementation.
    """
    config = WKSConfig.load()

    # Check daemon config exists
    if config.daemon is None:
        return StageResult(
            announce="Installing daemon service...",
            result="Error: daemon configuration not found in config.json",
            output={"error": "daemon section missing from config"},
            success=False,
        )

    # Validate backend type
    backend_type = config.daemon.type
    if backend_type not in _BACKEND_REGISTRY:
        return StageResult(
            announce="Installing daemon service...",
            result=f"Error: Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})",
            output={
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

        # Get Python path and project root
        python_path = sys.executable
        import wks
        project_root = Path(wks.__file__).parent.parent

        # Install via backend implementation
        result = daemon_impl.install_service(python_path, project_root)
        # Remove 'success' from output - it's handled by StageResult.success
        output = {k: v for k, v in result.items() if k != "success"}

        return StageResult(
            announce="Installing daemon service...",
            result=f"Daemon service installed successfully (label: {result.get('label', 'unknown')})",
            output=output,
            success=result.get("success", True),
        )
    except NotImplementedError as e:
        return StageResult(
            announce="Installing daemon service...",
            result=f"Error: Service installation not supported for backend '{backend_type}'",
            output={"error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce="Installing daemon service...",
            result=f"Error installing service: {e}",
            output={"error": str(e)},
            success=False,
        )
