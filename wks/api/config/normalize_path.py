"""Normalize a path for WKS.

Expands user home directory (~) and returns an absolute path
WITHOUT resolving symlinks. Use this for monitor rules
where symlink pointers must be preserved.
"""

from pathlib import Path
from typing import TypeVar, overload

T = TypeVar("T", str, Path)


@overload
def normalize_path(path: str) -> Path: ...


@overload
def normalize_path(path: Path) -> Path: ...


@overload
def normalize_path(path: None) -> None: ...


def normalize_path(path: str | Path | None) -> Path | None:
    """Expand user and return absolute path (no symlink resolution)."""
    if path is None:
        return None
    return Path(path).expanduser().absolute()
