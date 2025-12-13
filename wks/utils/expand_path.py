"""Expand user path (~/...) to absolute path."""

from pathlib import Path


def expand_path(path: str) -> Path:
    """Expand user path (~/...) to absolute path."""
    return Path(path).expanduser()
