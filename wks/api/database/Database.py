"""Database public API."""

from typing import Any

from ._AbstractImpl import _AbstractImpl
from .DatabaseConfig import DatabaseConfig


class Database:
    """Public API for database operations."""

    def __init__(self, database_config: DatabaseConfig, database_name: str):
        self.database_config = database_config
        self.prefix = database_config.prefix
        self.database_name = database_name
        self._impl: _AbstractImpl | None = None

    def __enter__(self):
        backend_type = self.database_config.type

        # Validate backend type using DatabaseConfig registry (single source of truth)
        from .DatabaseConfig import _BACKEND_REGISTRY

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        # Import database implementation class directly from backend _Impl module
        module = __import__(f"wks.api.database._{backend_type}._Impl", fromlist=[""])
        impl_class = module._Impl
        # _Impl expects: (database_config, database_name, collection_name)
        # database_name = MongoDB database name (prefix)
        # collection_name = MongoDB collection name (our database_name)
        self._impl = impl_class(self.database_config, self.prefix, self.database_name)
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

    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        """Update multiple documents matching the filter.

        Returns:
            Number of documents modified
        """
        return self._impl.update_many(filter, update)  # type: ignore[union-attr]

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._impl.delete_many(filter)  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._impl.find(filter, projection)  # type: ignore[union-attr]

    @classmethod
    def list_databases(cls, database_config: DatabaseConfig) -> list[str]:
        """List all databases (collections) in the prefix database.

        Args:
            database_config: Database configuration

        Returns:
            List of database names. All collections in the `<prefix>` database.

        Example:
            ```python
            databases = Database.list_databases(database_config)
            # Returns: ["monitor", "vault"] for collections in the "wks" database
            ```
        """
        with cls(database_config, "_") as database:
            client = database.get_client()
            # Get the database object using the prefix
            database_obj = client[database_config.prefix]
            # List all collections in the database
            # Collections are named after the database name (e.g., "monitor", "vault")
            # The prefix is the MongoDB database name, not part of the collection name
            all_collections = database_obj.list_collection_names()
            return sorted(all_collections)

    @classmethod
    def query(
        cls,
        database_config: DatabaseConfig,
        database_name: str,
        query_filter: dict[str, Any] | None = None,
        limit: int = 50,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query database with simple pass-through interface.

        Args:
            database_config: Database configuration
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
            result = Database.query(database_config, "monitor", {"status": "active"}, limit=10)
            # Returns: {"results": [...], "count": 5}
            ```
        """
        with cls(database_config, database_name) as database:
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
        database_prefix = database_name or self.prefix
        return self._impl._client[database_prefix]  # type: ignore[attr-defined]
