"""Common utility functions for WKS."""

import hashlib
import os
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore

from .constants import WKS_HOME_EXT


def file_checksum(path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


# Package version - cached for performance
_VERSION_CACHE = None


def get_package_version() -> str:
    """Get WKS package version (cached)."""
    global _VERSION_CACHE
    if _VERSION_CACHE is None:
        try:
            _VERSION_CACHE = importlib_metadata.version("wks")
        except Exception:
            _VERSION_CACHE = "unknown"
    return _VERSION_CACHE


def expand_path(path: str) -> Path:
    """Expand user path (~/...) to absolute path."""
    return Path(path).expanduser()


def get_wks_home() -> Path:
    """Get WKS home directory path.

    Checks WKS_HOME environment variable first, defaults to ~/.wks if not set.

    Returns:
        Path to WKS home directory

    Examples:
        >>> # WKS_HOME not set
        >>> get_wks_home()
        Path("/Users/user/.wks")
        >>> # WKS_HOME="/custom/path"
        >>> get_wks_home()
        Path("/custom/path")
    """
    wks_home_env = os.environ.get("WKS_HOME")
    if wks_home_env:
        return Path(wks_home_env).expanduser().resolve()

    # Check HOME environment variable (for test isolation)
    home_env = os.environ.get("HOME")
    if home_env:
        return Path(home_env) / WKS_HOME_EXT

    return Path.home() / WKS_HOME_EXT


def wks_home_path(*parts: str) -> Path:
    """Get path under WKS home directory.

    Args:
        *parts: Path components to join (e.g., "config.json", "mongodb", etc.)

    Returns:
        Absolute path under WKS home directory

    Examples:
        >>> wks_home_path("config.json")
        Path("/Users/user/.wks/config.json")
        >>> wks_home_path("mongodb", "data")
        Path("/Users/user/.wks/mongodb/data")
    """
    wks_home = get_wks_home()
    return wks_home / Path(*parts) if parts else wks_home


def canonicalize_path(path_str: str) -> str:
    """Normalize a path string for comparison.

    Expands user home directory (~) and resolves symlinks to create a
    canonical representation of the path. If resolution fails (e.g., path
    doesn't exist), returns the expanded path without resolution.

    Args:
        path_str: Path string to canonicalize (may include ~)

    Returns:
        Canonical path string (absolute, resolved)

    Examples:
        >>> canonicalize_path("~/Documents/file.txt")
        "/Users/user/Documents/file.txt"
        >>> canonicalize_path("/tmp/symlink")
        "/tmp/resolved_target"
    """
    path_obj = Path(path_str).expanduser()
    try:
        return str(path_obj.resolve(strict=False))
    except Exception:
        return str(path_obj)
