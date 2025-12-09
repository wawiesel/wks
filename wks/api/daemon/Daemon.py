"""Daemon public API."""

from pathlib import Path
from typing import Any

from .DaemonConfig import DaemonConfig, _BACKEND_REGISTRY
from ._AbstractImpl import _AbstractImpl


class Daemon:
    """Public API for daemon operations."""

    def __init__(self, daemon_config: DaemonConfig):
        self.daemon_config = daemon_config
        self._impl: _AbstractImpl | None = None

    def __enter__(self):
        backend_type = self.daemon_config.type

        # Validate backend type using DaemonConfig registry (single source of truth)
        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import daemon implementation class directly from backend _Impl module
        module = __import__(f"wks.api.daemon._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        self._impl = impl_class(self.daemon_config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Daemon implementations don't need cleanup, but we keep the pattern for consistency
        return False

    def get_service_status(self) -> dict[str, Any]:
        """Get daemon service status.

        Returns:
            Dictionary with service status information (installed, pid, etc.)
        """
        if not self._impl:
            raise RuntimeError("Daemon not initialized. Use as context manager first.")
        return self._impl.get_service_status()

    def install_service(self, python_path: str, project_root: Path) -> dict[str, Any]:
        """Install daemon as system service.

        Args:
            python_path: Path to Python interpreter
            project_root: Project root directory for PYTHONPATH

        Returns:
            Dictionary with installation result (success, label, plist_path, etc.)
        """
        if not self._impl:
            raise RuntimeError("Daemon not initialized. Use as context manager first.")
        return self._impl.install_service(python_path, project_root)

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon system service.

        Returns:
            Dictionary with uninstallation result
        """
        if not self._impl:
            raise RuntimeError("Daemon not initialized. Use as context manager first.")
        return self._impl.uninstall_service()

    def start_service(self) -> dict[str, Any]:
        """Start daemon via system service manager.

        Returns:
            Dictionary with start result
        """
        if not self._impl:
            raise RuntimeError("Daemon not initialized. Use as context manager first.")
        return self._impl.start_service()

    def stop_service(self) -> dict[str, Any]:
        """Stop daemon via system service manager.

        Returns:
            Dictionary with stop result
        """
        if not self._impl:
            raise RuntimeError("Daemon not initialized. Use as context manager first.")
        return self._impl.stop_service()

