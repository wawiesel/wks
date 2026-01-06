"""Normalize a path for WKS.

Expands user home directory (~) and returns an absolute path
WITHOUT resolving symlinks. Use this for monitor rules
where symlink pointers must be preserved.
"""

from pathlib import Path


def normalize_path(path: str | Path | None) -> Path:
    """Expand user and return absolute path (no symlink resolution)."""
    if path is None:
        raise ValueError("normalize_path requires a path")
    return Path(path).expanduser().absolute()
