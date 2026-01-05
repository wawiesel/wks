"""Expand user path (~/...) to absolute path."""

from pathlib import Path

from .normalize_path import normalize_path


def expand_path(path: str) -> Path:
    """Expand user path (~/...) to absolute path."""
    return normalize_path(path)
