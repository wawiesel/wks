"""Abstract base class for daemon implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class _AbstractImpl(ABC):
    """Abstract base class for platform-specific daemon implementations."""

    @abstractmethod
    def run(self) -> None:
        """Run the daemon main loop.
        
        This method should:
        - Monitor filesystem and update monitor database
        - Maintain vault links and sync with Obsidian
        - Provide MCP broker for AI agent access
        - Write status to daemon.json
        
        This method should run indefinitely until interrupted.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the daemon gracefully."""
        pass

    def install_service(self, python_path: str, project_root: Path) -> dict[str, Any]:
        """Install daemon as system service.
        
        Args:
            python_path: Path to Python interpreter
            project_root: Project root directory for PYTHONPATH
            
        Returns:
            Dictionary with installation result (success, label, plist_path, etc.)
            
        Raises:
            NotImplementedError: If service installation is not supported for this backend
        """
        raise NotImplementedError("Service installation not supported for this backend")

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon system service.
        
        Returns:
            Dictionary with uninstallation result
            
        Raises:
            NotImplementedError: If service uninstallation is not supported for this backend
        """
        raise NotImplementedError("Service uninstallation not supported for this backend")

    def get_service_status(self) -> dict[str, Any]:
        """Get daemon service status.
        
        Returns:
            Dictionary with service status information (installed, pid, etc.)
            
        Raises:
            NotImplementedError: If service status is not supported for this backend
        """
        raise NotImplementedError("Service status not supported for this backend")

    def start_service(self) -> dict[str, Any]:
        """Start daemon via system service manager.
        
        Returns:
            Dictionary with start result
            
        Raises:
            NotImplementedError: If service start is not supported for this backend
        """
        raise NotImplementedError("Service start not supported for this backend")

    def stop_service(self) -> dict[str, Any]:
        """Stop daemon via system service manager.
        
        Returns:
            Dictionary with stop result
            
        Raises:
            NotImplementedError: If service stop is not supported for this backend
        """
        raise NotImplementedError("Service stop not supported for this backend")

