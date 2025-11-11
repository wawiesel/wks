"""Display layer for WKS - CLI and MCP output formatting."""

from .base import Display
from .cli import CLIDisplay
from .mcp import MCPDisplay
from .context import get_display, is_mcp_context

__all__ = ["Display", "CLIDisplay", "MCPDisplay", "get_display", "is_mcp_context"]
