"""Compatibility shim for wks.config - imports from wks.api.config."""

# Re-export everything from the new location for backwards compatibility
from .api.config import (
    ConfigError,
    DisplayConfig,
    MetricsConfig,
    WKSConfig,
    get_config_path,
    get_home_dir,
)

# Backwards compatibility aliases
get_wks_home = get_home_dir
wks_home_path = get_home_dir

__all__ = [
    "ConfigError",
    "DisplayConfig",
    "MetricsConfig",
    "WKSConfig",
    "get_config_path",
    "get_home_dir",
    "get_wks_home",
    "wks_home_path",
]
