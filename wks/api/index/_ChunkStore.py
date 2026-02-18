"""MongoDB storage for index chunks."""

from typing import Any

from ._Chunk import _Chunk


class _ChunkStore:
    """Read/write chunks in a database collection, keyed by (index_name, uri)."""

    def __init__(self, db: Any):
        self._db = db

    def replace_uri(self, index_name: str, uri: str, checksum: str, chunks: list[_Chunk]) -> int:
        """Delete existing chunks for (index_name, uri) and insert new ones."""
        self._db.delete_many({"index_name": index_name, "uri": uri})
        if not chunks:
            return 0
        docs = [
            {
                "index_name": index_name,
                "uri": c.uri,
                "checksum": checksum,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "tokens": c.tokens,
                "is_continuation": c.is_continuation,
            }
            for c in chunks
        ]
        self._db.insert_many(docs)
        return len(docs)

    def get_all(self, index_name: str) -> list[_Chunk]:
        """Load all chunks for a named index."""
        return [
            _Chunk(
                text=doc["text"],
                uri=doc["uri"],
                chunk_index=doc["chunk_index"],
                tokens=doc["tokens"],
                is_continuation=doc["is_continuation"],
            )
            for doc in self._db.find({"index_name": index_name}, {"_id": 0})
        ]

    def count(self, index_name: str | None = None) -> int:
        """Count chunks, optionally filtered by index."""
        filt = {"index_name": index_name} if index_name else None
        return self._db.count_documents(filt)

    def uris(self, index_name: str) -> list[str]:
        """Distinct URIs in a named index."""
        seen: set[str] = set()
        for doc in self._db.find({"index_name": index_name}, {"uri": 1, "_id": 0}):
            seen.add(doc["uri"])
        return sorted(seen)

    def clear(self, index_name: str | None = None) -> int:
        """Delete chunks, optionally filtered by index."""
        filt = {"index_name": index_name} if index_name else {}
        return self._db.delete_many(filt)
