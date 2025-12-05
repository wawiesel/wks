"""Metrics configuration."""

from dataclasses import dataclass
from typing import Any


@dataclass
class MetricsConfig:
    """Metrics configuration."""

    fs_rate_short_window_secs: float = 10.0
    fs_rate_long_window_secs: float = 600.0
    fs_rate_short_weight: float = 0.8
    fs_rate_long_weight: float = 0.2

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "MetricsConfig":
        """Load metrics config from config dict."""
        metrics_cfg = cfg.get("metrics", {})
        return cls(
            fs_rate_short_window_secs=float(metrics_cfg.get("fs_rate_short_window_secs", 10.0)),
            fs_rate_long_window_secs=float(metrics_cfg.get("fs_rate_long_window_secs", 600.0)),
            fs_rate_short_weight=float(metrics_cfg.get("fs_rate_short_weight", 0.8)),
            fs_rate_long_weight=float(metrics_cfg.get("fs_rate_long_weight", 0.2)),
        )

