"""Display layer for WKS - CLI and MCP output formatting."""

from . import service as service_display
from .base import Display
from .cli import CLIDisplay
from .context import get_display, is_mcp_context
from .mcp import MCPDisplay

__all__ = [
    "Display",
    "CLIDisplay",
    "MCPDisplay",
    "get_display",
    "is_mcp_context",
    "service_display",
]
