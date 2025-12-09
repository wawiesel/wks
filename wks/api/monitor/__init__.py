"""Monitor API module."""

from .MonitorConfig import MonitorConfig
from ..schema_loader import register_from_schema

_models = register_from_schema("monitor")
MonitorCheckOutput = _models.get("MonitorCheckOutput")
MonitorSyncOutput = _models.get("MonitorSyncOutput")
MonitorStatusOutput = _models.get("MonitorStatusOutput")
MonitorFilterAddOutput = _models.get("MonitorFilterAddOutput")
MonitorFilterRemoveOutput = _models.get("MonitorFilterRemoveOutput")
MonitorFilterShowOutput = _models.get("MonitorFilterShowOutput")
MonitorPriorityAddOutput = _models.get("MonitorPriorityAddOutput")
MonitorPriorityRemoveOutput = _models.get("MonitorPriorityRemoveOutput")
MonitorPriorityShowOutput = _models.get("MonitorPriorityShowOutput")

__all__ = [
    "MonitorConfig",
    "MonitorCheckOutput",
    "MonitorSyncOutput",
    "MonitorStatusOutput",
    "MonitorFilterAddOutput",
    "MonitorFilterRemoveOutput",
    "MonitorFilterShowOutput",
    "MonitorPriorityAddOutput",
    "MonitorPriorityRemoveOutput",
    "MonitorPriorityShowOutput",
]
