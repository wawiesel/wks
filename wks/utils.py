"""Common utility functions for WKS."""

import hashlib
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    import importlib_metadata  # type: ignore



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


def find_matching_path_key(path_map: dict, candidate: str) -> str | None:
    """Find the key in a path map that canonically matches candidate.

    This function is useful for finding dictionary keys that represent paths,
    even if the key and candidate use different path representations (e.g., ~ vs absolute).

    Args:
        path_map: Dictionary with path strings as keys
        candidate: Path string to find a matching key for

    Returns:
        Matching key from path_map if found, None otherwise

    Examples:
        >>> path_map = {"~/Documents": 100, "/tmp": 50}
        >>> find_matching_path_key(path_map, "~/Documents")
        "~/Documents"
        >>> find_matching_path_key(path_map, "/Users/user/Documents")
        "~/Documents"
        >>> find_matching_path_key(path_map, "/nonexistent")
        None
    """
    candidate_norm = canonicalize_path(candidate)
    for key in path_map:
        if canonicalize_path(key) == candidate_norm:
            return key
    return None
