"""Diff module - File comparison operations."""

from .controller import DiffController
from .engines import ENGINES, get_engine

__all__ = [
    "ENGINES",
    "DiffController",
    "get_engine",
]
