"""Abstract base class for service implementations (system service installers)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ServiceStatus import ServiceStatus


class _AbstractImpl(ABC):
    """Abstract base class for platform-specific service implementations.

    Services install and manage the daemon as a system service (launchd on macOS).
    The daemon itself handles filesystem monitoring via `wksc daemon start`.
    """

    @abstractmethod
    def install_service(self, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install daemon as system service.

        Args:
            restrict_dir: Optional directory to restrict monitoring to

        Returns:
            Dictionary with installation result (success, label, plist_path, etc.)
        """
        pass

    @abstractmethod
    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon system service.

        Returns:
            Dictionary with uninstallation result
        """
        pass

    @abstractmethod
    def get_service_status(self) -> "ServiceStatus":
        """Get daemon service status.

        Returns:
            ServiceStatus object with service status information.
        """
        pass

    @abstractmethod
    def start_service(self) -> dict[str, Any]:
        """Start daemon via system service manager.

        Returns:
            Dictionary with start result
        """
        pass

    @abstractmethod
    def stop_service(self) -> dict[str, Any]:
        """Stop daemon via system service manager.

        Returns:
            Dictionary with stop result
        """
        pass
