from typing import Any, Literal

from ._AbstractBackend import _AbstractBackend
from .DatabaseConfig import DatabaseConfig


class Database(_AbstractBackend):
    def __init__(self, database_config: DatabaseConfig, database_name: str | None = None):
        self.database_config = database_config
        self.prefix = database_config.prefix
        self.name = database_name or self.prefix
        if self.name == "":
            raise ValueError("database_name cannot be empty string (use None for default)")
        self.type = database_config.type
        self._backend: _AbstractBackend | None = None

    def __enter__(self) -> "Database":
        backend_type = self.database_config.type

        from .DatabaseConfig import _BACKEND_REGISTRY

        backend_registry = _BACKEND_REGISTRY
        if backend_type not in backend_registry:
            raise ValueError(f"Unsupported backend type: {backend_type!r} (supported: {list(backend_registry.keys())})")

        module = __import__(f"wks.api.database._{backend_type}._Backend", fromlist=[""])
        backend_class = module._Backend

        self._backend = backend_class(self.database_config, self.database_config.prefix, self.name)
        self._backend.__enter__()  # Enter the backend context
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        if self._backend:
            self._backend.__exit__(exc_type, exc_val, exc_tb)
        self._backend = None
        return False

    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        return self._backend.count_documents(filter)  # type: ignore[union-attr]

    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        return self._backend.find_one(filter, projection)  # type: ignore[union-attr]

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        self._backend.update_one(filter, update, upsert)  # type: ignore[union-attr]

    def insert_one(self, document: dict[str, Any]) -> Any:
        return self._backend.insert_many([document])  # type: ignore[union-attr]

    def delete_one(self, filter: dict[str, Any]) -> int:
        return self._backend.delete_many(filter)  # type: ignore[union-attr]

    def insert_many(self, documents: list[dict[str, Any]]) -> Any:
        return self._backend.insert_many(documents)  # type: ignore[union-attr]

    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        return self._backend.update_many(filter, update)  # type: ignore[union-attr]

    def delete_many(self, filter: dict[str, Any]) -> int:
        return self._backend.delete_many(filter)  # type: ignore[union-attr]

    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        return self._backend.find(filter, projection)  # type: ignore[union-attr]

    @classmethod
    def list_databases(cls, database_config: DatabaseConfig) -> list[str]:
        with cls(database_config, "_") as database:
            client = database.get_client()
            database_obj = client[database_config.prefix]
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
        with cls(database_config, database_name) as database:
            results = list(database.find(query_filter, projection or {"_id": 0}).limit(limit))  # type: ignore[attr-defined]
            return {"results": results, "count": len(results)}

    def get_client(self) -> Any:
        if not self._backend:
            raise RuntimeError("Collection not initialized. Use as context manager first.")
        return self._backend._client  # type: ignore[attr-defined]

    def get_database(self, database_name: str | None = None) -> Any:
        if not self._backend:
            raise RuntimeError("Collection not initialized. Use as context manager first.")
        database_prefix = database_name or self.prefix
        return self._backend._client[database_prefix]  # type: ignore[attr-defined]
