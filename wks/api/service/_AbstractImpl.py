from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ServiceStatus import ServiceStatus


class _AbstractImpl(ABC):
    @abstractmethod
    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        pass

    @abstractmethod
    def uninstall_service(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_service_status(self) -> "ServiceStatus":
        pass

    @abstractmethod
    def start_service(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def stop_service(self) -> dict[str, Any]:
        pass
