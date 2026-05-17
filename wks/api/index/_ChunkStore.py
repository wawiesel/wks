import re
from typing import Any

from ._Chunk import _Chunk

_SEARCH_INDEX_NAME = "wks_chunk_text_search"
_TERM_RE = re.compile(r"[A-Za-z0-9_]+")
_FALLBACK_TEXT_SCAN_LIMIT = 10_000


class _ChunkStore:
    def __init__(self, db: Any):
        self._db = db

    def replace_uri(self, index_name: str, uri: str, checksum: str, chunks: list[_Chunk]) -> int:
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

    def ensure_search_indexes(self) -> str:
        try:
            return str(self._db.create_index([("text", "text")], name=_SEARCH_INDEX_NAME))
        except Exception as exc:
            raise RuntimeError(f"Failed to create text search index {_SEARCH_INDEX_NAME}: {exc}") from exc

    def get_all(self, index_name: str) -> list[_Chunk]:
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

    def search_text(self, index_name: str, query: str, limit: int) -> list[_Chunk]:
        if limit <= 0:
            return []
        try:
            cursor = self._db.find(
                {"index_name": index_name, "$text": {"$search": query}},
                {
                    "_id": 0,
                    "uri": 1,
                    "chunk_index": 1,
                    "text": 1,
                    "tokens": 1,
                    "is_continuation": 1,
                    "score": {"$meta": "textScore"},
                },
            )
            docs = list(cursor.sort([("score", {"$meta": "textScore"})]).limit(limit))
            return [_chunk_from_doc(doc) for doc in docs]
        except Exception as exc:
            return self._search_text_fallback(index_name, query, limit, exc)

    def count(self, index_name: str | None = None) -> int:
        filt = {"index_name": index_name} if index_name else None
        return self._db.count_documents(filt)

    def document_count(self, index_name: str) -> int:
        return len(self._db.distinct("uri", {"index_name": index_name}))

    def uris(self, index_name: str, limit: int | None = None) -> list[str]:
        seen: set[str] = set()
        for doc in self._db.find({"index_name": index_name}, {"uri": 1, "_id": 0}):
            seen.add(doc["uri"])
            if limit is not None and len(seen) >= limit:
                break
        return sorted(seen)

    def clear(self, index_name: str | None = None) -> int:
        filt = {"index_name": index_name} if index_name else {}
        return self._db.delete_many(filt)

    def _search_text_fallback(self, index_name: str, query: str, limit: int, search_error: Exception) -> list[_Chunk]:
        total_chunks = self.count(index_name)
        if total_chunks > _FALLBACK_TEXT_SCAN_LIMIT:
            raise RuntimeError(
                f"Text search index is unavailable for '{index_name}' "
                f"({total_chunks} chunks exceeds fallback scan limit {_FALLBACK_TEXT_SCAN_LIMIT}). "
                "Run: wksc index optimize"
            ) from search_error
        terms = _query_terms(query)
        if not terms:
            return []
        pattern = "|".join(re.escape(term) for term in terms)
        docs = self._db.find(
            {"index_name": index_name, "text": {"$regex": pattern, "$options": "i"}},
            {"_id": 0},
        ).limit(limit)
        return [_chunk_from_doc(doc) for doc in docs]


def _query_terms(query: str) -> list[str]:
    return [term.lower() for term in _TERM_RE.findall(query) if term]


def _chunk_from_doc(doc: dict[str, Any]) -> _Chunk:
    return _Chunk(
        text=doc["text"],
        uri=doc["uri"],
        chunk_index=doc["chunk_index"],
        tokens=doc["tokens"],
        is_continuation=doc.get("is_continuation", False),
    )
