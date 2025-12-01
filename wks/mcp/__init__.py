"""MCP (Model Context Protocol) server for WKS.

MCP is the source of truth for all business logic, errors, warnings, and messages.

Note: Due to Python's limitation of not allowing both a file and directory with the same name,
the main MCP server code is in wks.mcp_server module. Import from there:
    from wks.mcp_server import MCPServer, call_tool, main
"""

# Export result types from submodule
from .result import MCPResult, Message, MessageType

__all__ = ["MCPResult", "Message", "MessageType"]
