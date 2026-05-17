from typing import Any

import mongomock
from pymongo.collection import Collection

from .._AbstractBackend import _AbstractBackend
from ..DatabaseConfig import DatabaseConfig
from ._client import _get_mongomock_client
from ._Data import _Data as _DatabaseConfigData


class _Backend(_AbstractBackend):
    def __init__(self, database_config: DatabaseConfig, database_name: str, collection_name: str):
        if not isinstance(database_config.data, _DatabaseConfigData):
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
        self._collection = None
        return False

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return self._collection.count_documents(filter or {})  # type: ignore[union-attr]

    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._collection.find_one(filter, projection)  # type: ignore[union-attr]

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        self._collection.update_one(filter, update, upsert=upsert)  # type: ignore[union-attr]

    def insert_many(self, documents: list[dict[str, Any]]) -> Any:
        return self._collection.insert_many(documents)  # type: ignore[union-attr]

    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        result = self._collection.update_many(filter, update)  # type: ignore[union-attr]
        return result.modified_count

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._collection.delete_many(filter).deleted_count  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._collection.find(filter or {}, projection)  # type: ignore[union-attr]

    def create_index(self, keys: Any, **kwargs: Any) -> Any:
        return self._collection.create_index(keys, **kwargs)  # type: ignore[union-attr]

    def distinct(self, key: str, filter: dict[str, Any] | None = None) -> list[Any]:
        return self._collection.distinct(key, filter or {})  # type: ignore[union-attr]

    def list_collection_names(self) -> list[str]:
        if self._client is None:
            raise RuntimeError("MongoMock client not initialized")
        return self._client[self.database_name].list_collection_names()
