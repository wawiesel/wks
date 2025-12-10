"""Service public API."""

import platform
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..StageResult import StageResult
from . import (
    ServiceInstallOutput,
    ServiceStartOutput,
    ServiceStatusOutput,
    ServiceStopOutput,
    ServiceUninstallOutput,
)
from .ServiceConfig import ServiceConfig, _BACKEND_REGISTRY
from ._AbstractImpl import _AbstractImpl

if TYPE_CHECKING:
    from pydantic import BaseModel


class Service:
    """Public API for service operations."""

    def __init__(self, service_config: ServiceConfig):
        self.service_config = service_config
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
    def validate_backend_type(
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
            error_msg = f"Unsupported service backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
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

    def start_via_service(self) -> ServiceStartOutput:
        """Start service via service manager.

        Returns:
            ServiceStartOutput schema object
        """
        result = self.start_service()
        if "success" not in result:
            raise KeyError("start_service() result missing required 'success' field")
        success = result["success"]

        if success:
            if "label" not in result:
                raise KeyError("start_service() result missing required 'label' field when success=True")
            message = f"Service started successfully (label: {result['label']})"
            errors = []
        else:
            if "error" not in result:
                raise KeyError("start_service() result missing required 'error' field when success=False")
            message = f"Error starting service: {result['error']}"
            errors = [result["error"]]

        return ServiceStartOutput(
            errors=errors,
            warnings=[],
            message=message,
            running=success,
        )

    @staticmethod
    def start_directly(backend_type: str) -> ServiceStartOutput:
        """Start service directly as background process.

        Returns:
            ServiceStartOutput schema object
        """
        if backend_type not in _BACKEND_REGISTRY:
            return ServiceStartOutput(
                errors=[f"Unsupported service backend type: {backend_type!r}"],
                warnings=[],
                message=f"Error starting service: unsupported backend {backend_type!r}",
                running=False,
            )
        python_path = sys.executable
        service_module = f"wks.api.service._{backend_type}._Impl"

        try:
            process = subprocess.Popen(
                [python_path, "-m", service_module],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return ServiceStartOutput(
                errors=[],
                warnings=[],
                message=f"Service started successfully (PID: {process.pid})",
                running=True,
            )
        except Exception as e:
            return ServiceStartOutput(
                errors=[str(e)],
                warnings=[],
                message=f"Error starting service: {e}",
                running=False,
            )

    def __enter__(self):
        backend_type = self.service_config.type

        # Validate backend type using DaemonConfig registry (single source of truth)
        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import daemon implementation class directly from backend _Impl module
        module = __import__(f"wks.api.service._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        self._impl = impl_class(self.service_config)
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
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.get_service_status()

    def install_service(self, python_path: str, project_root: Path, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install service as system service.

        Args:
            python_path: Path to Python interpreter
            project_root: Project root directory for PYTHONPATH
            restrict_dir: Optional directory to restrict monitoring to

        Returns:
            Dictionary with installation result (success, label, plist_path, etc.)
        """
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.install_service(python_path, project_root, restrict_dir=restrict_dir)

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall system service.

        Returns:
            Dictionary with uninstallation result
        """
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.uninstall_service()

    def start_service(self) -> dict[str, Any]:
        """Start service via system service manager.

        Returns:
            Dictionary with start result
        """
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.start_service()

    def run(self, restrict_dir: Path | None = None) -> None:
        """Run the service loop directly (non-service mode)."""
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.run(restrict_dir=restrict_dir)

    def stop_service(self) -> dict[str, Any]:
        """Stop service via system service manager.

        Returns:
            Dictionary with stop result
        """
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.stop_service()
