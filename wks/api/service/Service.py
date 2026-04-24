import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ServiceStatus import ServiceStatus

from pydantic import BaseModel

from ..config.StageResult import StageResult
from . import ServiceStartOutput
from ._AbstractImpl import _AbstractImpl
from .ServiceConfig import _BACKEND_REGISTRY, ServiceConfig


class Service:
    def __init__(self, service_config: ServiceConfig):
        self.service_config = service_config
        self._impl: _AbstractImpl | None = None

    @staticmethod
    def detect_os() -> str:
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
        if backend_type not in _BACKEND_REGISTRY:
            error_msg = (
                f"Unsupported service backend type: {backend_type!r} (supported: {list(_BACKEND_REGISTRY.keys())})"
            )
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

    def start_via_service(self) -> BaseModel:
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

    def __enter__(self):
        backend_type = self.service_config.type

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        module = __import__(f"wks.api.service._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        self._impl = impl_class(self.service_config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def get_service_status(self) -> "ServiceStatus":
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.get_service_status()

    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.install_service(restrict_dir=restrict_dir)

    def uninstall_service(self) -> dict[str, Any]:
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.uninstall_service()

    def start_service(self) -> dict[str, Any]:
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.start_service()

    def stop_service(self) -> dict[str, Any]:
        if not self._impl:
            raise RuntimeError("Service not initialized. Use as context manager first.")
        return self._impl.stop_service()
