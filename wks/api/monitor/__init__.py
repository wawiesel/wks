"""Monitor API module."""

from wks.api.config.output_models import output_model

MonitorCheckOutput = output_model(
    "MonitorCheckOutput", "path", "is_monitored", "reason", "priority", "decisions", "success"
)
MonitorSyncOutput = output_model("MonitorSyncOutput", "message", "files_synced", "files_skipped", "success")
MonitorStatusOutput = output_model(
    "MonitorStatusOutput", "database", "tracked_files", "issues", "time_based_counts", "last_sync", "success"
)
MonitorFilterAddOutput = output_model(
    "MonitorFilterAddOutput", "message", "value_stored", "already_exists", "validation_failed", "success"
)
MonitorFilterRemoveOutput = output_model(
    "MonitorFilterRemoveOutput", "message", "value_removed", "not_found", "success"
)
MonitorFilterShowOutput = output_model("MonitorFilterShowOutput", "list_name", "available_lists", "items", "count")
MonitorPriorityAddOutput = output_model(
    "MonitorPriorityAddOutput",
    "message",
    "path_stored",
    "new_priority",
    "old_priority",
    "created",
    "already_exists",
    "success",
)
MonitorPriorityRemoveOutput = output_model(
    "MonitorPriorityRemoveOutput", "message", "path_removed", "priority", "not_found", "success"
)
MonitorPriorityShowOutput = output_model("MonitorPriorityShowOutput", "priority_directories", "count", "validation")

__all__ = [
    "MonitorCheckOutput",
    "MonitorFilterAddOutput",
    "MonitorFilterRemoveOutput",
    "MonitorFilterShowOutput",
    "MonitorPriorityAddOutput",
    "MonitorPriorityRemoveOutput",
    "MonitorPriorityShowOutput",
    "MonitorStatusOutput",
    "MonitorSyncOutput",
]
