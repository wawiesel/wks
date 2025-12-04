from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .diff.config import DiffConfig
from .monitor.config import MonitorConfig
from .transform.config import CacheConfig, TransformConfig
from .utils import get_wks_home
from .vault.config import VaultConfig

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
        if (
            not self.uri.startswith("mongodb://")
            and not self.uri.startswith("mongodb+srv://")
            and not self.uri.startswith("mongodb")
        ):
            raise ConfigError(f"db.uri must start with 'mongodb://' (found: {self.uri!r})")

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> MongoSettings:
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
    def from_config(cls, cfg: dict[str, Any]) -> MetricsConfig:
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
    def from_config(cls, cfg: dict[str, Any]) -> DisplayConfig:
        display_cfg = cfg.get("display", {})
        return cls(
            timestamp_format=display_cfg.get("timestamp_format", DEFAULT_TIMESTAMP_FORMAT),
        )


@dataclass
class WKSConfig:
    """Top-level configuration for all WKS layers.

    Diff configuration is optional. When a ``\"diff\"`` section is present in the
    raw config it is validated and attached as a :class:`DiffConfig`. If that
    section is omitted entirely, ``diff`` is left as ``None`` and diff-specific
    features are simply unavailable.
    """

    vault: VaultConfig
    monitor: MonitorConfig
    mongo: MongoSettings
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    diff: DiffConfig | None = None
    transform: TransformConfig = field(
        default_factory=lambda: TransformConfig(
            cache=CacheConfig(location=".wks/transform/cache", max_size_bytes=1073741824),
            engines={},
            database="wks.transform",
        )
    )
    display: DisplayConfig = field(default_factory=DisplayConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> WKSConfig:
        """Load and validate config from file."""
        if path is None:
            path = get_config_path()

        if not path.exists():
            raise ConfigError(f"Configuration file not found at {path}")

        try:
            with path.open() as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file {path}: {e}") from e

        try:
            mongo = MongoSettings.from_config(raw)
            # Pass the raw config (which contains the 'monitor' key)
            monitor = MonitorConfig.from_config_dict(raw)
            vault = VaultConfig.from_config_dict(raw)
            metrics = MetricsConfig.from_config(raw)
            diff = DiffConfig.from_config_dict(raw) if "diff" in raw else None
            transform = TransformConfig.from_config_dict(raw)
            display = DisplayConfig.from_config(raw)

            return cls(
                vault=vault,
                monitor=monitor,
                mongo=mongo,
                metrics=metrics,
                diff=diff,
                transform=transform,
                display=display,
            )
        except (ValidationError, KeyError, ValueError, Exception) as e:
            # Catching Exception to cover VaultConfigError/TransformConfigError if they bubble up
            # Ideally we should import them to catch specifically, but ConfigError wrapper is fine.
            raise ConfigError(f"Configuration validation failed: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        """Convert WKSConfig instance to a dictionary for serialization.

        Handles nested Pydantic models by calling .model_dump().
        """
        data = asdict(self)
        if isinstance(self.monitor, MonitorConfig):
            data["monitor"] = self.monitor.model_dump()
        # Add other Pydantic models here as they are migrated
        return data

    def save(self, path: Path | None = None) -> None:
        """Save the current configuration to a JSON file.

        Uses atomic write (write to temp file, then rename) to prevent corruption.
        Never deletes the existing config file - only overwrites it atomically.
        """
        if path is None:
            path = get_config_path()

        # Atomic write: write to temp file first, then rename
        # This prevents corruption if the write is interrupted
        temp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with temp_path.open("w") as fh:
                json.dump(self.to_dict(), fh, indent=4)
            # Atomic rename - this is the only operation that modifies the real file
            temp_path.replace(path)
        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise


def get_config_path() -> Path:
    """Get path to WKS config file."""
    config_path = get_wks_home() / "config.json"
    return config_path
