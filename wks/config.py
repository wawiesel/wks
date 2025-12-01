from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional, List

from .constants import WKS_HOME_EXT
from .utils import wks_home_path, get_wks_home
from .transform.config import TransformConfig
from .vault.config import VaultConfig
from .monitor.config import MonitorConfig, ValidationError as MonitorValidationError

DEFAULT_MONGO_URI = "mongodb://localhost:27017/"
DEFAULT_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


@dataclass
class MongoSettings:
    """Normalized MongoDB connection settings."""
    uri: str

    def __post_init__(self):
        if not self.uri:
            self.uri = DEFAULT_MONGO_URI
        if not self.uri.startswith("mongodb://") and not self.uri.startswith("mongodb+srv://"):
            if not self.uri.startswith("mongodb"):
                raise ConfigError(f"db.uri must start with 'mongodb://' (found: {self.uri!r})")

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "MongoSettings":
        db_cfg = cfg.get("db", {})
        return cls(
            uri=db_cfg.get("uri", DEFAULT_MONGO_URI),
        )


@dataclass
class MetricsConfig:
    """Metrics configuration."""
    fs_rate_short_window_secs: float = 10.0
    fs_rate_long_window_secs: float = 600.0
    fs_rate_short_weight: float = 0.8
    fs_rate_long_weight: float = 0.2

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "MetricsConfig":
        metrics_cfg = cfg.get("metrics", {})
        return cls(
            fs_rate_short_window_secs=float(metrics_cfg.get("fs_rate_short_window_secs", 10.0)),
            fs_rate_long_window_secs=float(metrics_cfg.get("fs_rate_long_window_secs", 600.0)),
            fs_rate_short_weight=float(metrics_cfg.get("fs_rate_short_weight", 0.8)),
            fs_rate_long_weight=float(metrics_cfg.get("fs_rate_long_weight", 0.2)),
        )


@dataclass
class DisplayConfig:
    """Display configuration."""
    timestamp_format: str = DEFAULT_TIMESTAMP_FORMAT

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "DisplayConfig":
        display_cfg = cfg.get("display", {})
        return cls(
            timestamp_format=display_cfg.get("timestamp_format", DEFAULT_TIMESTAMP_FORMAT),
        )


@dataclass
class WKSConfig:
    """Top-level WKS configuration."""
    vault: VaultConfig
    monitor: MonitorConfig
    mongo: MongoSettings
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    transform: TransformConfig = field(default_factory=lambda: TransformConfig(cache=None, engines={}))  # Placeholder default
    display: DisplayConfig = field(default_factory=DisplayConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "WKSConfig":
        """Load and validate config from file."""
        if path is None:
            path = get_config_path()

        if not path.exists():
            raise ConfigError(f"Configuration file not found at {path}")

        try:
            with open(path, "r") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file {path}: {e}")

        try:
            mongo = MongoSettings.from_config(raw)
            monitor = MonitorConfig.from_config_dict(raw)
            vault = VaultConfig.from_config_dict(raw)
            metrics = MetricsConfig.from_config(raw)

            transform = TransformConfig.from_config_dict(raw)
            display = DisplayConfig.from_config(raw)

            return cls(
                vault=vault,
                monitor=monitor,
                mongo=mongo,
                metrics=metrics,
                transform=transform,
                display=display,
            )
        except (MonitorValidationError, KeyError, ValueError, Exception) as e:
            # Catching Exception to cover VaultConfigError/TransformConfigError if they bubble up
            # Ideally we should import them to catch specifically, but ConfigError wrapper is fine.
            raise ConfigError(f"Configuration validation failed: {e}")


def get_config_path() -> Path:
    """Get path to WKS config file."""
    return get_wks_home() / "config.json"

# Backwards compatibility - DEPRECATED


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Compatibility wrapper returning a dict-shaped config for legacy callers.

    New code should prefer WKSConfig.load() and dataclasses directly. This
    function exists so older modules (MCP tools, vault helpers, etc.) that
    still expect a plain dict can continue to operate without duplicating
    config parsing logic.
    """
    try:
        cfg = WKSConfig.load(path)
    except Exception:
        # Preserve previous behaviour – callers must handle empty config.
        return {}

    data: Dict[str, Any] = asdict(cfg)

    # Provide a normalized DB section for helpers that expect "db.uri".
    data["db"] = {"uri": cfg.mongo.uri}

    # Provide legacy, flattened transform keys expected by MCP tools and tests.
    t_cfg = cfg.transform
    t_dict = data.setdefault("transform", {})
    t_dict["cache_location"] = str(t_cfg.cache.location)
    t_dict["cache_max_size_bytes"] = t_cfg.cache.max_size_bytes
    t_dict.setdefault("database", t_cfg.database)
    t_dict.setdefault("default_engine", t_cfg.default_engine)

    return data
