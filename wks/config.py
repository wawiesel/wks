from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, List

from .constants import WKS_HOME_EXT
from .utils import wks_home_path, get_wks_home
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
class VaultConfig:
    """Vault configuration."""
    base_dir: Path
    wks_dir: str = ".wks"
    update_frequency_seconds: int = 3600
    database: str = "wks.vault"

    def __post_init__(self):
        if not isinstance(self.base_dir, Path):
            self.base_dir = Path(self.base_dir)
        
        if self.base_dir.is_absolute() and not self.base_dir.exists():
             pass

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "VaultConfig":
        vault_cfg = cfg.get("vault", {})
        if "base_dir" not in vault_cfg:
             raise ConfigError("vault.base_dir is required")
        
        return cls(
            base_dir=Path(vault_cfg["base_dir"]),
            wks_dir=vault_cfg.get("wks_dir", ".wks"),
            update_frequency_seconds=vault_cfg.get("update_frequency_seconds", 3600),
            database=vault_cfg.get("database", "wks.vault"),
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
class WKSConfig:
    """Top-level WKS configuration."""
    vault: VaultConfig
    monitor: MonitorConfig
    mongo: MongoSettings
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    transform: Dict[str, Any] = field(default_factory=dict)
    display: Dict[str, Any] = field(default_factory=dict)

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
            vault = VaultConfig.from_config(raw)
            metrics = MetricsConfig.from_config(raw)
            
            return cls(
                vault=vault,
                monitor=monitor,
                mongo=mongo,
                metrics=metrics,
                transform=raw.get("transform", {}),
                display=raw.get("display", {}),
            )
        except (MonitorValidationError, KeyError, ValueError) as e:
            raise ConfigError(f"Configuration validation failed: {e}")

def get_config_path() -> Path:
    """Get path to WKS config file."""
    return get_wks_home() / "config.json"

# Backwards compatibility - DEPRECATED
def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """DEPRECATED: Use WKSConfig.load() instead.
    
    Returns a dict representation for temporary compatibility.
    """
    try:
        cfg = WKSConfig.load(path)
        return {
            "vault": {
                "base_dir": str(cfg.vault.base_dir),
                "wks_dir": cfg.vault.wks_dir,
                "update_frequency_seconds": cfg.vault.update_frequency_seconds,
                "database": cfg.vault.database,
            },
            "monitor": {
                "include_paths": cfg.monitor.include_paths,
                "exclude_paths": cfg.monitor.exclude_paths,
                "include_dirnames": cfg.monitor.include_dirnames,
                "exclude_dirnames": cfg.monitor.exclude_dirnames,
                "include_globs": cfg.monitor.include_globs,
                "exclude_globs": cfg.monitor.exclude_globs,
                "database": cfg.monitor.database,
                "managed_directories": cfg.monitor.managed_directories,
                "touch_weight": cfg.monitor.touch_weight,
                "priority": cfg.monitor.priority,
                "max_documents": cfg.monitor.max_documents,
                "prune_interval_secs": cfg.monitor.prune_interval_secs,
            },
            "db": {"uri": cfg.mongo.uri},
            "display": cfg.display,
        }
    except ConfigError:
        return {}
