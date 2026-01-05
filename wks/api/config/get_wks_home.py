"""Utility to discover WKS home directory."""

import os
from pathlib import Path

from .normalize_path import normalize_path


def get_wks_home() -> Path:
    """Get WKS home directory based on WKS_HOME or default to ~/.wks."""
    wks_home_env = os.environ.get("WKS_HOME")
    if wks_home_env:
        return normalize_path(wks_home_env)
    return Path.home() / ".wks"
