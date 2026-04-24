from wks.api.config.output_models import output_model

McpListOutput = output_model("McpListOutput", "targets", "count")
McpInstallOutput = output_model("McpInstallOutput", "success", "name", "command")
McpUninstallOutput = output_model("McpUninstallOutput", "success", "name", "command")

__all__ = [
    "McpInstallOutput",
    "McpListOutput",
    "McpUninstallOutput",
]
