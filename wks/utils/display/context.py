"""Context detection and display factory for CLI vs MCP environments."""

import os
import sys
from collections.abc import Callable
from typing import Literal

from .Display import Display

DisplayMode = Literal["cli", "mcp"]


def is_mcp_context() -> bool:
    """Detect if we're running in an MCP context.

    Returns:
        True if MCP environment detected, False otherwise
    """
    if os.getenv("MCP_MODE") == "1":
        return True

    if os.getenv("MCP_SERVER") is not None:
        return True

    return not sys.stdout.isatty() and os.getenv("TERM") is None


def _display_factories() -> dict[DisplayMode, Callable[[], Display]]:
    """Factory registry for display implementations."""
    from wks.cli.display import CLIDisplay

    return {"cli": CLIDisplay, "mcp": CLIDisplay}


def _resolve_mode(mode: DisplayMode | None) -> DisplayMode:
    """Resolve requested mode to a supported display mode."""
    if mode is not None:
        if mode not in _display_factories():
            raise ValueError(f"Unsupported display mode: {mode}")
        return mode
    return "mcp" if is_mcp_context() else "cli"


def get_display(mode: DisplayMode | None = None) -> Display:
    """Get appropriate display implementation.

    Args:
        mode: Explicit display mode ("cli" or "mcp"). If None, auto-detect.

    Returns:
        Display implementation (currently CLI for both modes).
    """
    factories = _display_factories()
    resolved_mode = _resolve_mode(mode)
    factory = factories.get(resolved_mode)
    if factory is None:
        raise RuntimeError(f"No display factory registered for mode: {resolved_mode}")
    return factory()


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
