"""Shared embedding utilities for indexing and semantic search."""

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=4)
def _load_embedder(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover - exercised in integration/runtime
        raise RuntimeError(
            "sentence-transformers is required for embedding workflows. Install it in the WKS environment."
        ) from exc
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    """Embed text rows and return an L2-normalized float32 matrix."""
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0 (found: {batch_size})")
    if len(texts) == 0:
        raise ValueError("texts cannot be empty")
    embedder = _load_embedder(model_name)
    matrix = embedder.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError(f"embedding matrix must be 2D (found ndim={matrix.ndim})")
    if matrix.shape[0] != len(texts):
        raise ValueError(f"embedding row count must match text count (rows={matrix.shape[0]}, texts={len(texts)})")
    return matrix


def cosine_scores(query_embedding: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine scores for normalized vectors."""
    if query_embedding.ndim != 1:
        raise ValueError(f"query_embedding must be 1D (found ndim={query_embedding.ndim})")
    if matrix.ndim != 2:
        raise ValueError(f"matrix must be 2D (found ndim={matrix.ndim})")
    if matrix.shape[1] != query_embedding.shape[0]:
        raise ValueError(
            f"embedding dimensions do not match (matrix_dim={matrix.shape[1]}, query_dim={query_embedding.shape[0]})"
        )
    return matrix @ query_embedding
