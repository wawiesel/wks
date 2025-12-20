"""Daemon module - filesystem watcher runtime."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("daemon")
DaemonStatusOutput: type[BaseModel] = _models["DaemonStatusOutput"]
DaemonStartOutput: type[BaseModel] = _models["DaemonStartOutput"]
DaemonStopOutput: type[BaseModel] = _models["DaemonStopOutput"]
DaemonClearOutput: type[BaseModel] = _models["DaemonClearOutput"]
DaemonClearLogOutput: type[BaseModel] = _models["DaemonClearLogOutput"]

__all__ = [
    "DaemonClearLogOutput",
    "DaemonClearOutput",
    "DaemonStartOutput",
    "DaemonStatusOutput",
    "DaemonStopOutput",
]
