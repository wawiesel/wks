"""Service module - service management and installation."""

from wks.api.config.output_models import output_model

ServiceClearOutput = output_model("ServiceClearOutput", "cleared", "message")
ServiceStatusOutput = output_model("ServiceStatusOutput", "running", "installed", "pid", "log_path")
ServiceStartOutput = output_model("ServiceStartOutput", "running", "message")
ServiceStopOutput = output_model("ServiceStopOutput", "stopped", "message")
ServiceInstallOutput = output_model("ServiceInstallOutput", "installed", "message")
ServiceUninstallOutput = output_model("ServiceUninstallOutput", "uninstalled", "message")

__all__ = [
    "ServiceClearOutput",
    "ServiceInstallOutput",
    "ServiceStartOutput",
    "ServiceStatusOutput",
    "ServiceStopOutput",
    "ServiceUninstallOutput",
]
