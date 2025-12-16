"""Daemon module - filesystem watcher runtime."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("daemon")
DaemonStatusOutput: type[BaseModel] = _models["DaemonStatusOutput"]
DaemonStartOutput: type[BaseModel] = _models["DaemonStartOutput"]
DaemonRunOutput: type[BaseModel] = _models["DaemonRunOutput"]
DaemonStopOutput: type[BaseModel] = _models["DaemonStopOutput"]

__all__ = [
    "DaemonRunOutput",
    "DaemonStartOutput",
    "DaemonStatusOutput",
    "DaemonStopOutput",
]
