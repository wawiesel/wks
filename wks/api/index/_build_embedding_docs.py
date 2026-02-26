"""Build embedding documents for storage."""

from typing import Any

import numpy as np

from ._Chunk import _Chunk


def build_embedding_docs(
    index_name: str,
    embedding_model: str,
    embedding_mode: str,
    chunks: list[_Chunk],
    embeddings: np.ndarray,
) -> list[dict[str, Any]]:
    """Build embedding documents aligned with chunk rows."""
    if embeddings.ndim != 2:
        raise ValueError(f"embeddings must be 2D (found ndim={embeddings.ndim})")
    if embeddings.shape[0] != len(chunks):
        raise ValueError(f"embedding rows must match chunks (rows={embeddings.shape[0]}, chunks={len(chunks)})")
    return [
        {
            "index_name": index_name,
            "embedding_model": embedding_model,
            "embedding_mode": embedding_mode,
            "uri": chunk.uri,
            "chunk_index": chunk.chunk_index,
            "tokens": chunk.tokens,
            "text": chunk.text,
            "embedding": embeddings[i].tolist(),
        }
        for i, chunk in enumerate(chunks)
    ]
