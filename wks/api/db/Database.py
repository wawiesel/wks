"""Database public API."""

from typing import Any

from ._AbstractImpl import _AbstractImpl
from .DbConfig import DbConfig


class Database:
    """Public API for database operations."""

    def __init__(self, db_config: DbConfig, database_name: str):
        self.db_config = db_config
        self.db_name = db_config.prefix
        self.database_name = database_name
        self._impl: _AbstractImpl | None = None

    def __enter__(self):
        backend_type = self.db_config.type

        # Validate backend type using DbConfig registry (single source of truth)
        from .DbConfig import _BACKEND_REGISTRY

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import database implementation class directly from backend _Impl module
        module = __import__(f"wks.api.db._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        self._impl = impl_class(self.db_config, self.db_name, self.database_name)
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
    def query(
        cls,
        db_config: DbConfig,
        database_name: str,
        query_filter: dict[str, Any] | None = None,
        limit: int = 50,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query database with simple pass-through interface.

        Args:
            db_config: Database configuration
            database_name: Database name (e.g., "monitor"). Prefix from config is automatically prepended.
                Database names must NOT include the prefix - only specify the database name itself.
            query_filter: Query filter dict. Examples:
                - `{"status": "active"}` - exact match
                - `{"age": {"$gt": 18}}` - greater than
                - `{}` or `None` - all documents
            limit: Maximum number of documents to return (default: 50)
            projection: Fields to include/exclude. Examples:
                - `{"_id": 0}` - exclude _id (default)
                - `{"name": 1, "age": 1}` - include only name and age

        Returns:
            Dict with keys:
                - `results`: List of matching documents
                - `count`: Number of documents returned (may be less than limit)

        Example:
            ```python
            result = Database.query(db_config, "monitor", {"status": "active"}, limit=10)
            # Returns: {"results": [...], "count": 5}
            ```
        """
        with cls(db_config, database_name) as database:
            results = list(database.find(query_filter, projection or {"_id": 0}).limit(limit))  # type: ignore[attr-defined]
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
