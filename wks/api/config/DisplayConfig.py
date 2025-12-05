"""Display configuration."""

from dataclasses import dataclass
from typing import Any

DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class DisplayConfig:
    """Display configuration."""

    timestamp_format: str = DEFAULT_TIMESTAMP_FORMAT

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "DisplayConfig":
        """Load display config from config dict."""
        display_cfg = cfg.get("display", {})
        return cls(
            timestamp_format=display_cfg.get("timestamp_format", DEFAULT_TIMESTAMP_FORMAT),
        )

