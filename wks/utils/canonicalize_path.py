"""Normalize a path string for comparison.

Expands user home directory (~) and resolves symlinks to create a
canonical representation of the path. If resolution fails (e.g., path
doesn't exist), returns the expanded path without resolution.
"""

from pathlib import Path


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
