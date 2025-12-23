"""Get transform engine helper (UNO: single function)."""

from ._ENGINES import ENGINES
from .TransformEngine import TransformEngine


def get_engine(name: str) -> TransformEngine | None:
    """Get transform engine by name.

    Args:
        name: Engine name (e.g., "docling")

    Returns:
        Engine instance or None if not found
    """
    return ENGINES.get(name)
