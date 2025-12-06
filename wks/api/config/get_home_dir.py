"""Get WKS home directory path or path under it."""

import os
from pathlib import Path

from ...constants import WKS_HOME_EXT


def get_home_dir(*parts: str) -> Path:
    """Get WKS home directory path or path under it.

    If no parts are provided, returns the base WKS home directory.
    If parts are provided, returns a path under the WKS home directory.

    Checks WKS_HOME environment variable first, defaults to ~/.wks if not set.

    Args:
        *parts: Optional path components to join (e.g., "config.json", "mongodb", etc.)

    Returns:
        Absolute path to WKS home directory or subpath under it

    Examples:
        >>> get_home_dir()
        Path("/Users/user/.wks")
        >>> get_home_dir("config.json")
        Path("/Users/user/.wks/config.json")
        >>> get_home_dir("mongodb", "data")
        Path("/Users/user/.wks/mongodb/data")
    """
    wks_home_env = os.environ.get("WKS_HOME")
    if wks_home_env:
        wks_home = Path(wks_home_env).expanduser().resolve()
    else:
        # Check HOME environment variable (for test isolation)
        home_env = os.environ.get("HOME")
        if home_env:
            wks_home = Path(home_env) / WKS_HOME_EXT
        else:
            wks_home = Path.home() / WKS_HOME_EXT

    return wks_home / Path(*parts) if parts else wks_home
