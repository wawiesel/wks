"""Shared helpers for MCP socket locations."""

from pathlib import Path

from wks.api.config.get_home_dir import get_home_dir


def mcp_socket_path() -> Path:
    """Return the canonical MCP broker socket path."""
    return get_home_dir("mcp.sock")


__all__ = ["mcp_socket_path"]
