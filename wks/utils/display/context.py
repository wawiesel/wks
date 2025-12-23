"""Context detection and display factory for CLI vs MCP environments."""

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from .Display import Display

DisplayMode = Literal["cli", "mcp"]


@dataclass(frozen=True)
class DisplayContext:
    """Centralized display factory with explicit mode resolution."""

    factories: Mapping[DisplayMode, Callable[[], Display]] = field(
        default_factory=lambda: MappingProxyType(DisplayContext._build_factories())
    )

    def __post_init__(self) -> None:
        missing_modes = {"cli", "mcp"} - set(self.factories)
        if missing_modes:
            raise ValueError(f"Display factories missing required modes: {sorted(missing_modes)}")

    @staticmethod
    def _build_factories() -> dict[DisplayMode, Callable[[], Display]]:
        from wks.cli.display import CLIDisplay

        return {"cli": CLIDisplay, "mcp": CLIDisplay}

    def is_mcp_context(self) -> bool:
        """Detect if we're running in an MCP context."""

        if os.getenv("MCP_MODE") == "1":
            return True

        if os.getenv("MCP_SERVER") is not None:
            return True

        return not sys.stdout.isatty() and os.getenv("TERM") is None

    def _resolve_mode(self, mode: DisplayMode | None) -> DisplayMode:
        if mode is not None:
            if mode not in self.factories:
                raise ValueError(f"Unsupported display mode: {mode}")
            return mode
        return "mcp" if self.is_mcp_context() else "cli"

    def get_display(self, mode: DisplayMode | None = None) -> Display:
        """Get appropriate display implementation."""

        resolved_mode = self._resolve_mode(mode)
        factory = self.factories.get(resolved_mode)
        if factory is None:
            raise RuntimeError(f"No display factory registered for mode: {resolved_mode}")
        return factory()

    def add_display_argument(self, parser) -> None:
        """Add --display argument to an argparse parser."""

        default_mode = "mcp" if self.is_mcp_context() else "cli"

        parser.add_argument(
            "--display",
            choices=["cli", "mcp"],
            default=default_mode,
            help=f"Output display format (default: {default_mode}, auto-detected)",
        )


display_context = DisplayContext()
