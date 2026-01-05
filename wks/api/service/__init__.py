"""Service module - service management and installation."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_package(__package__)
ServiceStatusOutput: type[BaseModel] = _models["ServiceStatusOutput"]
ServiceStartOutput: type[BaseModel] = _models["ServiceStartOutput"]
ServiceStopOutput: type[BaseModel] = _models["ServiceStopOutput"]
ServiceInstallOutput: type[BaseModel] = _models["ServiceInstallOutput"]
ServiceUninstallOutput: type[BaseModel] = _models["ServiceUninstallOutput"]

__all__ = [
    "ServiceInstallOutput",
    "ServiceStartOutput",
    "ServiceStatusOutput",
    "ServiceStopOutput",
    "ServiceUninstallOutput",
]
