"""Context detection and display factory for CLI vs MCP environments."""

import os
import sys
from typing import Literal, Optional

from .base import Display
from .cli import CLIDisplay
from .mcp import MCPDisplay

DisplayMode = Literal["cli", "mcp"]


def is_mcp_context() -> bool:
    """Detect if we're running in an MCP context.

    Returns:
        True if MCP environment detected, False otherwise
    """
    # Check environment variables that MCP might set
    if os.getenv("MCP_MODE") == "1":
        return True

    if os.getenv("MCP_SERVER") is not None:
        return True

    # Check if stdin/stdout are pipes (common in MCP)
    # But also check we're not in a regular terminal with pipes
    # If TERM is not set and we're piped, likely MCP
    return not sys.stdout.isatty() and os.getenv("TERM") is None


def get_display(mode: Optional[DisplayMode] = None) -> Display:
    """Get appropriate display implementation.

    Args:
        mode: Explicit display mode ("cli" or "mcp")
              If None, auto-detect based on context

    Returns:
        Display implementation (CLIDisplay or MCPDisplay)
    """
    if mode is None:
        # Auto-detect
        mode = "mcp" if is_mcp_context() else "cli"

    if mode == "mcp":
        return MCPDisplay()
    elif mode == "cli":
        return CLIDisplay()
    else:
        raise ValueError(f"Invalid display mode: {mode}. Must be 'cli' or 'mcp'")


def add_display_argument(parser) -> None:
    """Add --display argument to an argparse parser.

    Args:
        parser: argparse.ArgumentParser instance
    """
    default_mode = "mcp" if is_mcp_context() else "cli"

    parser.add_argument(
        "--display",
        choices=["cli", "mcp"],
        default=default_mode,
        help=f"Output display format (default: {default_mode}, auto-detected)",
    )
