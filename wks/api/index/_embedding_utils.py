"""Shared embedding utilities for indexing and semantic search."""

from functools import lru_cache
from pathlib import Path

import numpy as np

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


@lru_cache(maxsize=4)
def _load_embedder(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover - exercised in integration/runtime
        raise RuntimeError(
            "sentence-transformers is required for embedding workflows. Install it in the WKS environment."
        ) from exc
    return SentenceTransformer(model_name)


@lru_cache(maxsize=2)
def _load_clip_model_and_processor(model_name: str):
    try:
        from transformers import CLIPModel, CLIPProcessor
    except Exception as exc:  # pragma: no cover - exercised in integration/runtime
        raise RuntimeError("transformers with CLIP support is required for image-text embedding workflows.") from exc
    model = CLIPModel.from_pretrained(model_name)
    model.eval()
    processor = CLIPProcessor.from_pretrained(model_name)
    return processor, model


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


def embed_clip_texts(texts: list[str], model_name: str, batch_size: int) -> np.ndarray:
    """Embed text rows with CLIP text encoder and return normalized float32 matrix."""
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0 (found: {batch_size})")
    if len(texts) == 0:
        raise ValueError("texts cannot be empty")

    try:
        import torch
    except Exception as exc:  # pragma: no cover - exercised in integration/runtime
        raise RuntimeError("torch is required for CLIP text embedding workflows.") from exc

    processor, model = _load_clip_model_and_processor(model_name)
    vectors: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        inputs = processor(text=batch, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            batch_vectors = model.get_text_features(**inputs)
            batch_vectors = batch_vectors / batch_vectors.norm(dim=-1, keepdim=True)
        vectors.append(batch_vectors.cpu().numpy())

    matrix = np.vstack(vectors).astype(np.float32)
    if matrix.ndim != 2:
        raise ValueError(f"embedding matrix must be 2D (found ndim={matrix.ndim})")
    if matrix.shape[0] != len(texts):
        raise ValueError(f"embedding row count must match text count (rows={matrix.shape[0]}, texts={len(texts)})")
    return matrix


def is_supported_image_path(path: Path) -> bool:
    """Return True when path suffix is a supported image format."""
    return path.suffix.lower() in IMAGE_SUFFIXES


def embed_clip_images(image_paths: list[Path], model_name: str, batch_size: int) -> np.ndarray:
    """Embed image rows with CLIP image encoder and return normalized float32 matrix."""
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0 (found: {batch_size})")
    if len(image_paths) == 0:
        raise ValueError("image_paths cannot be empty")

    for image_path in image_paths:
        if not image_path.exists():
            raise ValueError(f"Image not found: {image_path}")
        if not is_supported_image_path(image_path):
            raise ValueError(f"Unsupported image extension: {image_path.suffix} (path={image_path})")

    try:
        import torch
        from PIL import Image
    except Exception as exc:  # pragma: no cover - exercised in integration/runtime
        raise RuntimeError("torch and Pillow are required for CLIP image embedding workflows.") from exc

    processor, model = _load_clip_model_and_processor(model_name)
    vectors: list[np.ndarray] = []
    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i : i + batch_size]
        batch_images = []
        for image_path in batch_paths:
            with Image.open(image_path) as image:
                batch_images.append(image.convert("RGB"))
        inputs = processor(images=batch_images, return_tensors="pt")
        with torch.no_grad():
            batch_vectors = model.get_image_features(**inputs)
            batch_vectors = batch_vectors / batch_vectors.norm(dim=-1, keepdim=True)
        vectors.append(batch_vectors.cpu().numpy())

    matrix = np.vstack(vectors).astype(np.float32)
    if matrix.ndim != 2:
        raise ValueError(f"embedding matrix must be 2D (found ndim={matrix.ndim})")
    if matrix.shape[0] != len(image_paths):
        raise ValueError(
            f"embedding row count must match image_paths count (rows={matrix.shape[0]}, image_paths={len(image_paths)})"
        )
    return matrix


def combine_modal_embeddings(
    image_embeddings: np.ndarray,
    text_embeddings: np.ndarray,
    image_text_weight: float,
) -> np.ndarray:
    """Combine normalized image and text vectors into normalized hybrid vectors."""
    if image_embeddings.ndim != 2:
        raise ValueError(f"image_embeddings must be 2D (found ndim={image_embeddings.ndim})")
    if text_embeddings.ndim != 2:
        raise ValueError(f"text_embeddings must be 2D (found ndim={text_embeddings.ndim})")
    if image_embeddings.shape != text_embeddings.shape:
        raise ValueError(
            "image_embeddings and text_embeddings must have identical shape "
            f"(image={image_embeddings.shape}, text={text_embeddings.shape})"
        )
    if not 0.0 <= image_text_weight <= 1.0:
        raise ValueError(f"image_text_weight must be in [0,1] (found: {image_text_weight})")

    combined = image_embeddings * image_text_weight + text_embeddings * (1.0 - image_text_weight)
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("combined embedding produced zero-length vectors")
    return (combined / norms).astype(np.float32)


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
