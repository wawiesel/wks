"""MCP installation management API."""

from ..schema_loader import register_from_schema

_models = register_from_schema("mcp")
McpListOutput = _models.get("McpListOutput")
McpInstallOutput = _models.get("McpInstallOutput")
McpUninstallOutput = _models.get("McpUninstallOutput")

__all__ = [
    "McpListOutput",
    "McpInstallOutput",
    "McpUninstallOutput",
]

