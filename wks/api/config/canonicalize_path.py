"""Normalize a path string for comparison.

Expands user home directory (~) and returns an absolute path WITHOUT
resolving symlinks. This ensures consistency with WKS monitor rules.
"""

from .normalize_path import normalize_path


def canonicalize_path(path_str: str) -> str:
    """Normalize a path string for comparison.

    Expands user home directory (~) and returns an absolute path
    WITHOUT resolving symlinks. This ensures consistency with WKS
    monitor rules which treat symlinks as distinct paths.

    Args:
        path_str: Path string to canonicalize (may include ~)

    Returns:
        Normalized absolute path string (no symlink resolution)

    Examples:
        >>> canonicalize_path("~/Documents/file.txt")
        "/Users/user/Documents/file.txt"
        >>> canonicalize_path("/tmp/symlink")
        "/tmp/symlink"
    """
    path_obj = normalize_path(path_str)
    return str(path_obj)
