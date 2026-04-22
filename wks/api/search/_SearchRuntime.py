"""Process-local runtime state for hot search queries.

This gives long-lived processes such as WKSM a place to keep lexical and
semantic query state resident between calls while still invalidating cleanly
when the indexed collections change.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

import numpy as np

from ..config.URI import URI
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from ..index._Chunk import _Chunk
from ..index._ChunkStore import _ChunkStore
from ..index._EmbeddingStore import _EmbeddingStore


@dataclass(frozen=True, slots=True)
class _CollectionFingerprint:
    """Cheap signature for detecting collection changes."""

    count: int
    newest_id: str | None


@dataclass(slots=True)
class _LexicalIndexState:
    """Hot lexical query state for a named index."""

    fingerprint: _CollectionFingerprint
    chunks: list[_Chunk]
    corpus: list[list[str]]
    bm25: Any | None


@dataclass(slots=True)
class _SemanticIndexState:
    """Hot semantic query state for a named index/model pair."""

    fingerprint: _CollectionFingerprint
    docs: list[dict[str, Any]]
    matrix: np.ndarray
    path_segments: list[frozenset[str]]


class _SearchRuntime:
    """Own process-local query state that survives across tool calls."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._config: WKSConfig | None = None
        self._config_path: str | None = None
        self._config_mtime_ns: int | None = None
        self._lexical_states: dict[str, _LexicalIndexState] = {}
        self._semantic_states: dict[tuple[str, str], _SemanticIndexState] = {}

    def reset(self) -> None:
        """Drop all cached config and query state."""
        with self._lock:
            self._config = None
            self._config_path = None
            self._config_mtime_ns = None
            self._lexical_states.clear()
            self._semantic_states.clear()

    def load_config(self) -> WKSConfig:
        """Load config once and invalidate caches when the config file changes."""
        path = WKSConfig.get_config_path()
        path_value = str(path)
        if path.exists():
            mtime_ns = path.stat().st_mtime_ns
            with self._lock:
                if self._config is not None and self._config_path == path_value and self._config_mtime_ns == mtime_ns:
                    return self._config
        else:
            return WKSConfig.load()

        config = WKSConfig.load()
        with self._lock:
            self._config = config
            self._config_path = path_value
            self._config_mtime_ns = mtime_ns
            self._lexical_states.clear()
            self._semantic_states.clear()
        return config

    def get_lexical_index_state(self, config: WKSConfig, index_name: str) -> _LexicalIndexState:
        """Return hot lexical state for one index, rebuilding on change."""
        with Database(config.database, "index") as db:
            fingerprint = _collection_fingerprint(db, {"index_name": index_name})
            with self._lock:
                cached = self._lexical_states.get(index_name)
                if cached is not None and cached.fingerprint == fingerprint:
                    return cached
            chunks = _ChunkStore(db).get_all(index_name)

        corpus = [chunk.text.lower().split() for chunk in chunks]
        bm25: Any | None = None
        if corpus:
            from rank_bm25 import BM25Okapi

            bm25 = BM25Okapi(corpus)

        state = _LexicalIndexState(
            fingerprint=fingerprint,
            chunks=chunks,
            corpus=corpus,
            bm25=bm25,
        )
        with self._lock:
            self._lexical_states[index_name] = state
        return state

    def get_semantic_index_state(
        self,
        config: WKSConfig,
        index_name: str,
        embedding_model: str,
    ) -> _SemanticIndexState:
        """Return hot semantic state for one index/model pair, rebuilding on change."""
        key = (index_name, embedding_model)
        collection_filter = {"index_name": index_name, "embedding_model": embedding_model}
        with Database(config.database, "index_embeddings") as db:
            fingerprint = _collection_fingerprint(db, collection_filter)
            with self._lock:
                cached = self._semantic_states.get(key)
                if cached is not None and cached.fingerprint == fingerprint:
                    return cached
            docs = _EmbeddingStore(db).get_all(index_name=index_name, embedding_model=embedding_model)

        if docs:
            matrix = np.asarray([doc["embedding"] for doc in docs], dtype=np.float32)
            path_segments = [_extract_path_segments(doc["uri"]) for doc in docs]
        else:
            matrix = np.empty((0, 0), dtype=np.float32)
            path_segments = []

        state = _SemanticIndexState(
            fingerprint=fingerprint,
            docs=docs,
            matrix=matrix,
            path_segments=path_segments,
        )
        with self._lock:
            self._semantic_states[key] = state
        return state


def _collection_fingerprint(db: Database, filter_doc: dict[str, Any]) -> _CollectionFingerprint:
    """Return a cheap collection signature for cache invalidation."""
    collection = db.get_database()[db.name]
    count = collection.count_documents(filter_doc)
    newest_doc = collection.find_one(filter_doc, {"_id": 1}, sort=[("_id", -1)])
    newest_id = str(newest_doc["_id"]) if newest_doc is not None else None
    return _CollectionFingerprint(count=count, newest_id=newest_id)


def _extract_path_segments(uri: str) -> frozenset[str]:
    """Precompute lowercase path segments for path-match score boosts."""
    try:
        path = URI.from_any(uri).path
    except Exception:
        return frozenset()
    parts = {part.lower() for part in path.parts}
    parts.add(path.stem.lower())
    return frozenset(parts)


_SEARCH_RUNTIME = _SearchRuntime()
