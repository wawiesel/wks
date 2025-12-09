"""Daemon module - service management and installation."""

from .DaemonConfig import DaemonConfig
from ..schema_loader import register_from_schema

_models = register_from_schema("daemon")
DaemonStatusOutput = _models.get("DaemonStatusOutput")
DaemonStartOutput = _models.get("DaemonStartOutput")
DaemonStopOutput = _models.get("DaemonStopOutput")
DaemonRestartOutput = _models.get("DaemonRestartOutput")
DaemonInstallOutput = _models.get("DaemonInstallOutput")
DaemonUninstallOutput = _models.get("DaemonUninstallOutput")

__all__ = [
    "DaemonConfig",
    "DaemonStatusOutput",
    "DaemonStartOutput",
    "DaemonStopOutput",
    "DaemonRestartOutput",
    "DaemonInstallOutput",
    "DaemonUninstallOutput",
]
