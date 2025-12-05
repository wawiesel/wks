"""Database collection factory and public API."""

from typing import Any

from ._AbstractImpl import _AbstractImpl
from .DbConfig import DbConfig


class DbCollection:
    """Public API for database collection operations."""

    def __init__(self, collection_name: str):
        from ...config import WKSConfig
        config = WKSConfig.load()
        self.db_config = config.db
        # If collection_name already contains ".", treat as "database.collection" for backwards compatibility
        # Otherwise, prepend prefix from config
        if "." in collection_name:
            self.db_name, self.coll_name = collection_name.split(".", 1)
        else:
            self.db_name = self.db_config.prefix
            self.coll_name = collection_name
        self._impl: _AbstractImpl | None = None

    def __enter__(self):
        backend_type = self.db_config.type

        # Validate backend type using DbConfig registry (single source of truth)
        if backend_type not in DbConfig._BACKEND_REGISTRY:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(DbConfig._BACKEND_REGISTRY.keys())})")

        # Import collection class directly from backend _Impl module
        module = __import__(f"wks.api.db._{backend_type}._Impl", fromlist=[""])
        collection_class = getattr(module, "_Impl")
        self._impl = collection_class(self.db_config, self.db_name, self.coll_name)
        self._impl.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._impl:
            return self._impl.__exit__(exc_type, exc_val, exc_tb)
        return False

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return self._impl.count_documents(filter)  # type: ignore[union-attr]

    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._impl.find_one(filter, projection)  # type: ignore[union-attr]

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        self._impl.update_one(filter, update, upsert)  # type: ignore[union-attr]

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._impl.delete_many(filter)  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._impl.find(filter, projection)  # type: ignore[union-attr]

    @classmethod
    def query(cls, collection_name: str, query_filter: dict[str, Any] | None = None, limit: int = 50, projection: dict[str, Any] | None = None) -> dict[str, Any]:
        """Query database with simple pass-through interface.

        Args:
            collection_name: Collection name (e.g., "monitor"). Prefix from config is automatically prepended.
                For backwards compatibility, "database.collection" format is also accepted.
            query_filter: Query filter dict (MongoDB-style). Examples:
                - `{"status": "active"}` - exact match
                - `{"age": {"$gt": 18}}` - greater than
                - `{"name": {"$regex": "^A"}}` - regex match
                - `{}` or `None` - all documents
            limit: Maximum number of documents to return (default: 50)
            projection: Fields to include/exclude. Examples:
                - `{"_id": 0}` - exclude _id (default)
                - `{"name": 1, "age": 1}` - include only name and age
                - `{"password": 0}` - exclude password field

        Returns:
            Dict with keys:
                - `results`: List of matching documents
                - `count`: Number of documents returned (may be less than limit)

        Example:
            ```python
            result = DbCollection.query("monitor", {"status": "active"}, limit=10)
            # Returns: {"results": [...], "count": 5}
            ```
        """
        with cls(collection_name) as collection:
            results = list(collection.find(query_filter, projection or {"_id": 0}).limit(limit))  # type: ignore[attr-defined]
            return {"results": results, "count": len(results)}

    def get_client(self) -> Any:
        """Get the underlying database client (for code that needs direct access)."""
        if not self._impl:
            raise RuntimeError("Collection not initialized. Use as context manager first.")
        return self._impl._client  # type: ignore[attr-defined]

    def get_database(self, database_name: str | None = None) -> Any:
        """Get the underlying database object (for code that needs direct access)."""
        if not self._impl:
            raise RuntimeError("Collection not initialized. Use as context manager first.")
        db_name = database_name or self.db_name
        return self._impl._client[db_name]  # type: ignore[attr-defined]
