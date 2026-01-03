"""Service status DTO."""

from dataclasses import dataclass


@dataclass
class ServiceStatus:
    """Status of the system service daemon."""

    installed: bool
    """Whether the service is installed (systemd unit or launchd plist exists)."""

    unit_path: str
    """Path to the service definition file."""

    running: bool = False
    """Whether the service is currently running."""

    pid: int | None = None
    """Process ID of the running service, or None if not running."""
