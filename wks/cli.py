"""
WKS command-line interface.

This module maintains backward compatibility by re-exporting from the new modular structure.
The actual implementation is in wks.cli.main and wks.cli.commands.*
"""

from .cli.main import main
from .cli.commands.config import show_config
from .config import load_config

# Re-export for backward compatibility
__all__ = ["main", "show_config", "load_config"]
