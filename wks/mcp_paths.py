"""Shared helpers for MCP socket locations."""

from pathlib import Path

from .utils import wks_home_path


def mcp_socket_path() -> Path:
    """Return the canonical MCP broker socket path."""
    return wks_home_path("mcp.sock")


__all__ = ["mcp_socket_path"]
