"""Expand user path (~/...) to absolute path."""

from pathlib import Path


def expand_path(path: str) -> Path:
    """Expand user path (~/...) to absolute path."""
    from wks.utils.normalize_path import normalize_path

    return normalize_path(path)
