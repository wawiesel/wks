"""Get path to WKS config file."""

from pathlib import Path

from .get_home_dir import get_home_dir


def get_config_path() -> Path:
    """Get path to WKS config file."""
    return get_home_dir("config.json")

