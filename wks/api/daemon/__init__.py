"""Daemon module - filesystem watcher runtime."""

from .Daemon import Daemon
from ..schema_loader import register_from_schema

_models = register_from_schema("daemon")
DaemonStatusOutput = _models.get("DaemonStatusOutput")
DaemonStartOutput = _models.get("DaemonStartOutput")
DaemonStopOutput = _models.get("DaemonStopOutput")

__all__ = [
    "Daemon",
    "DaemonStatusOutput",
    "DaemonStartOutput",
    "DaemonStopOutput",
]
