"""Output schemas for daemon commands."""

from typing import Any

from pydantic import Field

from ._base import BaseOutputSchema
from ._registry import register_output_schema


class DaemonStatusOutput(BaseOutputSchema):
    """Output schema for daemon status command.

    All fields must always be present for consistency.
    """
    running: bool = Field(..., description="Whether daemon is running")
    type: str = Field(..., description="How daemon is running: 'service', 'terminal', or empty string")
    pid: int = Field(..., description="Process ID if running, -1 if not running")
    data: dict[str, Any] = Field(..., description="Additional data (service/terminal specific)")


class DaemonStartOutput(BaseOutputSchema):
    """Output schema for daemon start command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    method: str = Field(..., description="How daemon was started: 'service' or 'direct', empty string if not applicable")
    label: str = Field(..., description="Service label (if started as service), empty string if not applicable")
    pid: int = Field(..., description="Process ID if started directly, -1 if not applicable")
    action: str = Field(..., description="Action taken (e.g., 'bootstrapped', 'kickstarted'), empty string if not applicable")


class DaemonStopOutput(BaseOutputSchema):
    """Output schema for daemon stop command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    label: str = Field(..., description="Service label, empty string if not applicable")
    message: str = Field(..., description="Additional message, empty string if not applicable")
    supported: list[str] = Field(..., description="List of supported backend types (when error), empty list if not applicable")


class DaemonInstallOutput(BaseOutputSchema):
    """Output schema for daemon install command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    label: str = Field(..., description="Service label")
    plist_path: str = Field(..., description="Path to plist file, empty string if not applicable")
    already_loaded: bool = Field(..., description="Whether service was already loaded")
    plist_updated: bool = Field(..., description="Whether plist was updated")
    supported: list[str] = Field(..., description="List of supported backend types (when error), empty list if not applicable")


class DaemonUninstallOutput(BaseOutputSchema):
    """Output schema for daemon uninstall command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    label: str = Field(..., description="Service label, empty string if not applicable")
    supported: list[str] = Field(..., description="List of supported backend types (when error), empty list if not applicable")


class DaemonRestartOutput(BaseOutputSchema):
    """Output schema for daemon restart command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    method: str = Field(..., description="How daemon was started: 'service' or 'direct', empty string if not applicable")
    label: str = Field(..., description="Service label, empty string if not applicable")
    pid: int = Field(..., description="Process ID if started directly, -1 if not applicable")
    action: str = Field(..., description="Action taken (e.g., 'bootstrapped', 'kickstarted'), empty string if not applicable")
    restarted: bool = Field(..., description="Whether daemon was restarted")


class DaemonReinstallOutput(BaseOutputSchema):
    """Output schema for daemon reinstall command."""
    type: str = Field(..., description="Platform type (e.g., 'macos')")
    label: str = Field(..., description="Service label")
    plist_path: str = Field(..., description="Path to plist file, empty string if not applicable")
    already_loaded: bool = Field(..., description="Whether service was already loaded")
    plist_updated: bool = Field(..., description="Whether plist was updated")
    supported: list[str] = Field(..., description="List of supported backend types (when error), empty list if not applicable")


# Register all schemas
register_output_schema("daemon", "status", DaemonStatusOutput)
register_output_schema("daemon", "start", DaemonStartOutput)
register_output_schema("daemon", "stop", DaemonStopOutput)
register_output_schema("daemon", "install", DaemonInstallOutput)
register_output_schema("daemon", "uninstall", DaemonUninstallOutput)
register_output_schema("daemon", "restart", DaemonRestartOutput)
register_output_schema("daemon", "reinstall", DaemonReinstallOutput)
