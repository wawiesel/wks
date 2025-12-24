"""Get diff engine helper."""

from ._ENGINES import ENGINES
from .DiffEngine import DiffEngine


def get_engine(name: str) -> DiffEngine | None:
    """Get diff engine by name.

    Args:
        name: Engine name (e.g., "bsdiff3", "myers")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
