"""MCP (Model Context Protocol) server for WKS."""

from .server import MCPServer, call_tool, main as server_main
from .paths import mcp_socket_path

__all__ = [
    "MCPServer",
    "call_tool",
    "server_main",
    "mcp_socket_path",
]
