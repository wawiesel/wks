"""Monitor API module.

This module provides monitor-related API functions following the one-file-per-function
pattern. Each function serves as the single source of truth for both CLI commands and
MCP tools.
"""

__all__ = ["monitor_app"]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "monitor_app":
        from .app import monitor_app
        return monitor_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
