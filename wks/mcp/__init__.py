"""MCP (Model Context Protocol) server for WKS.

MCP is the source of truth for all business logic, errors, warnings, and messages.
"""

# Export result types from submodule
from .result import MCPResult, Message, MessageType
# Export main server components
from .server import MCPServer, call_tool, main as server_main
from .client import proxy_stdio_to_socket
from .paths import mcp_socket_path
from .setup import install_mcp_configs
from .bridge import MCPBroker

__all__ = [
    "MCPResult",
    "Message",
    "MessageType",
    "MCPServer",
    "call_tool",
    "server_main",
    "proxy_stdio_to_socket",
    "mcp_socket_path",
    "install_mcp_configs",
    "MCPBroker",
]
