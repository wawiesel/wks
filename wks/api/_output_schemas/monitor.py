"""Output schemas for monitor commands."""

from typing import Any

from pydantic import Field

from ._base import BaseOutputSchema
from ._registry import register_output_schema


class MonitorCheckOutput(BaseOutputSchema):
    """Output schema for monitor check command."""
    path: str = Field(..., description="Path that was checked")
    is_monitored: bool = Field(..., description="Whether path would be monitored")
    reason: str = Field(..., description="Reason for monitoring decision")
    priority: float | None = Field(None, description="Priority score if monitored, None if not monitored")
    decisions: list[dict[str, str]] = Field(..., description="List of decision trace entries with symbol and message")
    success: bool = Field(..., description="Whether check completed successfully")


class MonitorSyncOutput(BaseOutputSchema):
    """Output schema for monitor sync command."""
    success: bool = Field(..., description="Whether sync completed successfully")
    message: str = Field(..., description="Summary message")
    files_synced: int = Field(..., description="Number of files successfully synced")
    files_skipped: int = Field(..., description="Number of files skipped")


class MonitorStatusOutput(BaseOutputSchema):
    """Output schema for monitor status command."""
    tracked_files: int = Field(..., description="Total number of tracked files")
    issues: list[str] = Field(..., description="List of issues found")
    priority_directories: list[dict[str, Any]] = Field(..., description="List of priority directories with validation status")
    time_based_counts: dict[str, int] = Field(..., description="Time-based file counts")
    success: bool = Field(..., description="Whether status check completed successfully")


class MonitorFilterAddOutput(BaseOutputSchema):
    """Output schema for monitor filter add command."""
    success: bool = Field(..., description="Whether add operation succeeded")
    message: str = Field(..., description="Result message")
    value_stored: str | None = Field(None, description="Value that was stored, None if failed")
    validation_failed: bool | None = Field(None, description="Whether validation failed, None if not applicable")
    already_exists: bool | None = Field(None, description="Whether value already existed, None if not applicable")
    error: str | None = Field(None, description="Error message if failed, None if succeeded")


class MonitorFilterRemoveOutput(BaseOutputSchema):
    """Output schema for monitor filter remove command."""
    success: bool = Field(..., description="Whether remove operation succeeded")
    message: str = Field(..., description="Result message")
    value_removed: str | None = Field(None, description="Value that was removed, None if not found")
    not_found: bool | None = Field(None, description="Whether value was not found, None if not applicable")
    error: str | None = Field(None, description="Error message if failed, None if succeeded")


class MonitorFilterShowOutput(BaseOutputSchema):
    """Output schema for monitor filter show command."""
    available_lists: list[str] | None = Field(None, description="List of available filter list names, None if showing specific list")
    list_name: str | None = Field(None, description="Name of list being shown, None if showing all lists")
    items: list[str] | None = Field(None, description="Items in the list, None if showing all lists")
    count: int | None = Field(None, description="Number of items in the list, None if showing all lists")
    success: bool = Field(..., description="Whether operation succeeded")
    error: str | None = Field(None, description="Error message if failed, None if succeeded")


class MonitorPriorityAddOutput(BaseOutputSchema):
    """Output schema for monitor priority add command."""
    success: bool = Field(..., description="Whether add operation succeeded")
    message: str = Field(..., description="Result message")
    path_stored: str = Field(..., description="Path that was stored")
    new_priority: float = Field(..., description="New priority value")
    created: bool = Field(..., description="Whether priority directory was created (True) or updated (False)")
    already_exists: bool = Field(..., description="Whether priority directory already existed")
    old_priority: float | None = Field(None, description="Previous priority value if updated, None if created")


class MonitorPriorityRemoveOutput(BaseOutputSchema):
    """Output schema for monitor priority remove command."""
    success: bool = Field(..., description="Whether remove operation succeeded")
    message: str = Field(..., description="Result message")
    path_removed: str | None = Field(None, description="Path that was removed, None if not found")
    priority: float | None = Field(None, description="Priority value that was removed, None if not found")
    not_found: bool | None = Field(None, description="Whether priority directory was not found, None if not applicable")


class MonitorPriorityShowOutput(BaseOutputSchema):
    """Output schema for monitor priority show command."""
    priority_directories: dict[str, float] = Field(..., description="Dictionary mapping paths to priority values")
    count: int = Field(..., description="Number of priority directories")
    validation: dict[str, dict[str, Any]] = Field(..., description="Validation status for each priority directory")


# Register all schemas
register_output_schema("monitor", "check", MonitorCheckOutput)
register_output_schema("monitor", "sync", MonitorSyncOutput)
register_output_schema("monitor", "status", MonitorStatusOutput)
register_output_schema("monitor", "filter_add", MonitorFilterAddOutput)
register_output_schema("monitor", "filter_remove", MonitorFilterRemoveOutput)
register_output_schema("monitor", "filter_show", MonitorFilterShowOutput)
register_output_schema("monitor", "priority_add", MonitorPriorityAddOutput)
register_output_schema("monitor", "priority_remove", MonitorPriorityRemoveOutput)
register_output_schema("monitor", "priority_show", MonitorPriorityShowOutput)
