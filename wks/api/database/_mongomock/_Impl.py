"""Mock MongoDB collection implementation using mongomock."""

from typing import Any

import mongomock
from pymongo.collection import Collection

from .._AbstractImpl import _AbstractImpl
from ..DatabaseConfig import DatabaseConfig
from ._DbConfigData import _DbConfigData

# Shared mongomock client for all instances (singleton pattern)
_shared_mongomock_client: mongomock.MongoClient | None = None


def _get_mongomock_client() -> mongomock.MongoClient:
    """Get or create shared mongomock client."""
    global _shared_mongomock_client
    if _shared_mongomock_client is None:
        _shared_mongomock_client = mongomock.MongoClient()
    return _shared_mongomock_client


class _Impl(_AbstractImpl):
    def __init__(self, db_config: DatabaseConfig, database_name: str, collection_name: str):
        if not isinstance(db_config.data, _DbConfigData):
            raise ValueError("MongoMock config data is required")
        self.database_name = database_name
        self.collection_name = collection_name
        self._client: mongomock.MongoClient | None = None
        self._collection: Collection | None = None

    def __enter__(self):
        self._client = _get_mongomock_client()
        self._collection = self._client[self.database_name][self.collection_name]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Don't close shared client - it's reused across instances
        # Only clear local references
        self._collection = None
        # Keep self._client set so get_client() works, but don't close it
        return False

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return self._collection.count_documents(filter or {})  # type: ignore[union-attr]

    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._collection.find_one(filter, projection)  # type: ignore[union-attr]

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        self._collection.update_one(filter, update, upsert=upsert)  # type: ignore[union-attr]

    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        result = self._collection.update_many(filter, update)  # type: ignore[union-attr]
        return result.modified_count

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._collection.delete_many(filter).deleted_count  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._collection.find(filter or {}, projection)  # type: ignore[union-attr]

    def list_collection_names(self) -> list[str]:
        return self._client[self.database_name].list_collection_names()  # type: ignore[union-attr]
