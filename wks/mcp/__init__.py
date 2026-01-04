"""MCP (Model Context Protocol) server for WKS."""

from wks.api.schema_loader import SchemaLoader
from .call_tool import call_tool
from .main import main as server_main
from .paths import mcp_socket_path
from .server import MCPServer


__all__ = [
    "MCPServer",
    "call_tool",
    "mcp_socket_path",
    "server_main",
]
