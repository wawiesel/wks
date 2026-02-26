"""MongoDB storage for index embeddings."""

from typing import Any


class _EmbeddingStore:
    """Read/write chunk embeddings keyed by (index_name, embedding_model)."""

    def __init__(self, db: Any):
        self._db = db

    def replace_index_model(self, index_name: str, embedding_model: str, docs: list[dict[str, Any]]) -> int:
        """Replace all embeddings for a given index/model pair."""
        self._db.delete_many({"index_name": index_name, "embedding_model": embedding_model})
        if not docs:
            return 0
        self._db.insert_many(docs)
        return len(docs)

    def replace_uri(
        self,
        index_name: str,
        embedding_model: str,
        uri: str,
        docs: list[dict[str, Any]],
    ) -> int:
        """Replace embeddings for a specific URI in a given index/model pair."""
        self._db.delete_many({"index_name": index_name, "embedding_model": embedding_model, "uri": uri})
        if not docs:
            return 0
        self._db.insert_many(docs)
        return len(docs)

    def get_all(self, index_name: str, embedding_model: str) -> list[dict[str, Any]]:
        """Load all embedding docs for a given index/model pair."""
        return list(
            self._db.find(
                {"index_name": index_name, "embedding_model": embedding_model},
                {"_id": 0},
            )
        )
