"""Get database helper function."""

from typing import Any

from .DbCollection import DbCollection
from .DbConfig import DbConfig


def get_database(db_config: DbConfig, database_name: str) -> Any:
    """Get the underlying database object (for code that needs direct access)."""
    collection = DbCollection(db_config, "_")
    collection.__enter__()
    # Don't call __exit__ so client stays alive
    return collection.get_database(database_name)

