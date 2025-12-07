"""Display layer for WKS - CLI and MCP output formatting."""

from .base import Display
from .cli import CLIDisplay
from .context import get_display, is_mcp_context
from .mcp import MCPDisplay

__all__ = [
    "CLIDisplay",
    "Display",
    "MCPDisplay",
    "get_display",
    "is_mcp_context",
]
