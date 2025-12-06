"""Get database client helper function."""

from typing import Any

from .DbCollection import DbCollection
from .DbConfig import DbConfig


def get_database_client(db_config: DbConfig) -> Any:
    """Get the underlying database client (for code that needs direct access)."""
    collection = DbCollection(db_config, "_")
    collection.__enter__()
    # Don't call __exit__ so client stays alive
    return collection.get_client()
