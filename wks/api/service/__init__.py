"""Service module - service management and installation."""

from .ServiceConfig import ServiceConfig
from ..schema_loader import register_from_schema

_models = register_from_schema("service")
ServiceStatusOutput = _models.get("ServiceStatusOutput")
ServiceStartOutput = _models.get("ServiceStartOutput")
ServiceStopOutput = _models.get("ServiceStopOutput")
ServiceInstallOutput = _models.get("ServiceInstallOutput")
ServiceUninstallOutput = _models.get("ServiceUninstallOutput")

__all__ = [
    "ServiceConfig",
    "ServiceStatusOutput",
    "ServiceStartOutput",
    "ServiceStopOutput",
    "ServiceInstallOutput",
    "ServiceUninstallOutput",
]
