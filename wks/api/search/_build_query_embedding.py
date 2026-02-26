"""Build query embeddings for semantic search modes."""

import numpy as np

from ..config.URI import URI
from ..index import _embedding_utils


def build_query_embedding(
    query: str,
    query_image: str,
    embedding_model: str,
    embedding_mode: str,
    image_text_weight: float | None,
) -> np.ndarray:
    """Build one normalized query embedding based on configured mode."""
    query_text = query.strip()
    query_image_value = query_image.strip()

    if embedding_mode == "text":
        if query_image_value:
            raise ValueError("query_image requires index embedding_mode 'image_text_combo'")
        if not query_text:
            raise ValueError("query is required for text semantic search")
        return _embedding_utils.embed_texts(texts=[query_text], model_name=embedding_model, batch_size=1)[0]

    if embedding_mode != "image_text_combo":
        raise ValueError(f"Unsupported embedding_mode: {embedding_mode}")

    if not query_text and not query_image_value:
        raise ValueError("Either query text or query_image is required for image-text semantic search")

    text_embedding: np.ndarray | None = None
    image_embedding: np.ndarray | None = None

    if query_text:
        text_embedding = _embedding_utils.embed_clip_texts(
            texts=[query_text],
            model_name=embedding_model,
            batch_size=1,
        )[0]

    if query_image_value:
        image_path = URI.from_any(query_image_value).path
        image_embedding = _embedding_utils.embed_clip_images(
            image_paths=[image_path],
            model_name=embedding_model,
            batch_size=1,
        )[0]

    if text_embedding is not None and image_embedding is not None:
        if image_text_weight is None:
            raise ValueError("index.image_text_weight is required when combining query text and query_image")
        return _embedding_utils.combine_modal_embeddings(
            image_embedding[np.newaxis, :],
            text_embedding[np.newaxis, :],
            image_text_weight,
        )[0]
    if image_embedding is not None:
        return image_embedding
    assert text_embedding is not None
    return text_embedding
