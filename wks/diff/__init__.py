"""Diff module - File comparison operations."""

from .controller import DiffController
from .engines import get_engine, ENGINES

__all__ = [
    "DiffController",
    "get_engine",
    "ENGINES",
]
