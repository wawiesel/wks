"""Daemon public API."""

import platform
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..StageResult import StageResult
from . import DaemonStartOutput
from .DaemonConfig import DaemonConfig, _BACKEND_REGISTRY
from ._AbstractImpl import _AbstractImpl

if TYPE_CHECKING:
    from pydantic import BaseModel


class Daemon:
    """Public API for daemon operations."""

    def __init__(self, daemon_config: DaemonConfig):
        self.daemon_config = daemon_config
        self._impl: _AbstractImpl | None = None

    @staticmethod
    def detect_os() -> str:
        """Detect the current operating system and check if backend is supported.

        Returns:
            OS identifier string matching platform.system().lower() (e.g., "darwin", "linux", "windows")

        Raises:
            RuntimeError: If OS backend directory does not exist
        """
        from pathlib import Path

        system = platform.system().lower()
        backend_dir = Path(__file__).parent / f"_{system}"
        if not backend_dir.exists():
            raise RuntimeError(f"Unsupported operating system: {system} (backend directory not found: {backend_dir})")
        return system

    @staticmethod
    def _validate_backend_type(
        result_obj: StageResult,
        backend_type: str,
        output_class: type["BaseModel"],
        status_field: str,
    ) -> bool:
        """Validate backend type and set error result if invalid.

        Args:
            result_obj: StageResult to update if validation fails
            backend_type: Backend type to validate
            output_class: Output schema class to instantiate
            status_field: Name of status field in output (e.g., "running", "stopped", "installed")

        Returns:
            True if valid, False if invalid (and result_obj is already set)
        """
        if backend_type not in _BACKEND_REGISTRY:
            error_msg = f"Unsupported daemon backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
            result_obj.result = f"Error: {error_msg}"
            result_obj.output = output_class(
                errors=[error_msg],
                warnings=[],
                message=error_msg,
                **{status_field: False},
            ).model_dump(mode="python")
            result_obj.success = False
            return False
        return True

    def _start_via_service(self) -> DaemonStartOutput:
        """Start daemon via service manager.

        Returns:
            DaemonStartOutput schema object
        """
        result = self.start_service()
        if "success" not in result:
            raise KeyError("start_service() result missing required 'success' field")
        success = result["success"]

        if success:
            if "label" not in result:
                raise KeyError("start_service() result missing required 'label' field when success=True")
            message = f"Daemon started successfully (label: {result['label']})"
            errors = []
        else:
            if "error" not in result:
                raise KeyError("start_service() result missing required 'error' field when success=False")
            message = f"Error starting daemon: {result['error']}"
            errors = [result["error"]]

        return DaemonStartOutput(
            errors=errors,
            warnings=[],
            message=message,
            running=success,
        )

    @staticmethod
    def _start_directly(backend_type: str) -> DaemonStartOutput:
        """Start daemon directly as background process.

        Returns:
            DaemonStartOutput schema object
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
            return DaemonStartOutput(
                errors=[],
                warnings=[],
                message=f"Daemon started successfully (PID: {process.pid})",
                running=True,
            )
        except Exception as e:
            return DaemonStartOutput(
                errors=[str(e)],
                warnings=[],
                message=f"Error starting daemon: {e}",
                running=False,
            )

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
