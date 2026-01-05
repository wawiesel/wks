"""Convenience entry point for invoking MCP tools directly."""

from typing import Any

from .server import MCPServer


def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a single MCP tool by name."""
    from wks.api.config.WKSConfig import WKSConfig

    server = MCPServer()
    registry = server.build_registry()
    if tool_name not in registry:
        return {"success": False, "data": {}, "error": f"Tool not found: {tool_name}"}
    return registry[tool_name](WKSConfig.load(), arguments)
