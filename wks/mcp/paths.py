"""Shared helpers for MCP socket locations."""

from pathlib import Path


def mcp_socket_path() -> Path:
    """Return the canonical MCP broker socket path."""
    from wks.api.config.WKSConfig import WKSConfig

    return WKSConfig.get_home_dir() / "mcp.sock"


__all__ = ["mcp_socket_path"]
