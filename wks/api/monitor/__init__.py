"""Monitor API module.

This module provides monitor-related API functions following the one-file-per-function
pattern. Each function serves as the single source of truth for both CLI commands and
MCP tools.
"""

__all__ = ["monitor_app"]

from .app import monitor_app
