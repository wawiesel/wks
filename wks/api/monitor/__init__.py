"""Monitor API module."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
MonitorCheckOutput: type[BaseModel] = _models["MonitorCheckOutput"]
MonitorSyncOutput: type[BaseModel] = _models["MonitorSyncOutput"]
MonitorStatusOutput: type[BaseModel] = _models["MonitorStatusOutput"]
MonitorFilterAddOutput: type[BaseModel] = _models["MonitorFilterAddOutput"]
MonitorFilterRemoveOutput: type[BaseModel] = _models["MonitorFilterRemoveOutput"]
MonitorFilterShowOutput: type[BaseModel] = _models["MonitorFilterShowOutput"]
MonitorPriorityAddOutput: type[BaseModel] = _models["MonitorPriorityAddOutput"]
MonitorPriorityRemoveOutput: type[BaseModel] = _models["MonitorPriorityRemoveOutput"]
MonitorPriorityShowOutput: type[BaseModel] = _models["MonitorPriorityShowOutput"]

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
