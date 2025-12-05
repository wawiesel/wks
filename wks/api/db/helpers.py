"""Database helper functions for downstream code."""

from typing import Any

from .DbCollection import DbCollection


def get_database_client() -> Any:
    """Get the underlying database client (for code that needs direct access)."""
    from ...config import WKSConfig
    config = WKSConfig.load()
    prefix = config.db.prefix
    collection = DbCollection("_")
    collection.__enter__()
    # Don't call __exit__ so client stays alive
    return collection.get_client()


def get_database(database_name: str) -> Any:
    """Get the underlying database object (for code that needs direct access)."""
    collection = DbCollection("_")
    collection.__enter__()
    # Don't call __exit__ so client stays alive
    return collection.get_database(database_name)
