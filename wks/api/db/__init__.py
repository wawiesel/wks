"""DB API module.

Provides database abstraction layer to avoid exposing database implementation details.
"""

from .DatabaseCollection import DatabaseCollection
from .query import query

__all__ = ["DatabaseCollection", "query"]
