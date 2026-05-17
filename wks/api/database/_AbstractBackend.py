from abc import ABC, abstractmethod
from typing import Any


class _AbstractBackend(ABC):
    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        pass

    @abstractmethod
    def find_one(self, filter: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> None:
        pass

    @abstractmethod
    def insert_many(self, documents: list[dict[str, Any]]) -> Any:
        pass

    @abstractmethod
    def update_many(self, filter: dict[str, Any], update: dict[str, Any]) -> int:
        pass

    @abstractmethod
    def delete_many(self, filter: dict[str, Any]) -> int:
        pass

    @abstractmethod
    def find(self, filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None) -> Any:
        pass

    def create_index(self, keys: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def distinct(self, key: str, filter: dict[str, Any] | None = None) -> list[Any]:
        raise NotImplementedError

    def list_collection_names(self) -> list[str]:
        raise NotImplementedError
