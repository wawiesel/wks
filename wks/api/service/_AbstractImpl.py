"""Abstract base class for daemon implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .FilesystemEvents import FilesystemEvents


class _AbstractImpl(ABC):
    """Abstract base class for platform-specific daemon implementations."""

    @abstractmethod
    def run(self, restrict_dir: Path | None = None) -> None:
        """Run the daemon main loop.
        
        Args:
            restrict_dir: Optional directory to restrict monitoring to. If None, uses configured paths
                from monitor.filter.include_paths. If specified, only monitors this directory and its
                subdirectories.
        
        This method should:
        - Monitor filesystem and update monitor database
        - Call monitor sync API for each filesystem event (modified, created, deleted, moved)
        - Run indefinitely until interrupted (KeyboardInterrupt or stop() called)
        
        This method should run indefinitely until interrupted.
        """
        pass

    @abstractmethod
    def get_filesystem_events(self) -> FilesystemEvents:
        """Get accumulated filesystem events since last call.
        
        This method should:
        - Return all filesystem events (modified, created, deleted, moved) accumulated since the last call
        - Clear the internal accumulator after returning (so subsequent calls return only new events)
        - Return an empty FilesystemEvents object if no events have occurred
        - Return ALL events without filtering (filtering happens in monitor sync)
        
        The daemon's main loop should call this method periodically (based on sync_interval_secs)
        and then call monitor sync (`wks.api.monitor.cmd_sync`) for each path in the returned events.
        Monitor sync will apply filtering using `explain_path()` and priority checks, maintaining
        a single source of truth for filter logic.
        
        Returns:
            FilesystemEvents object containing lists of paths for each event type.
            Paths are NOT filtered here - filtering is handled by monitor sync.
            After returning, the accumulated events are cleared.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the daemon gracefully."""
        pass

    def install_service(self, python_path: str, project_root: Path, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install daemon as system service.
        
        Args:
            python_path: Path to Python interpreter
            project_root: Project root directory for PYTHONPATH
            restrict_dir: Optional directory to restrict monitoring to (stored in service config)
            
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

