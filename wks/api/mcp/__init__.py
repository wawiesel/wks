"""MCP installation management API."""

from pydantic import BaseModel

from ..schema_loader import SchemaLoader

_models = SchemaLoader.register_from_schema("mcp")
McpListOutput: type[BaseModel] = _models["McpListOutput"]
McpInstallOutput: type[BaseModel] = _models["McpInstallOutput"]
McpUninstallOutput: type[BaseModel] = _models["McpUninstallOutput"]

__all__ = [
    "McpInstallOutput",
    "McpListOutput",
    "McpUninstallOutput",
]
