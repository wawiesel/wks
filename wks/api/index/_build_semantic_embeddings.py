"""Build semantic embedding matrices from indexed chunks."""

from pathlib import Path

import numpy as np

from ..config.URI import URI
from . import _embedding_utils
from ._Chunk import _Chunk


def build_semantic_embeddings(
    chunks: list[_Chunk],
    embedding_model: str,
    embedding_mode: str,
    image_text_weight: float | None,
    batch_size: int,
    source_image_path: Path | None = None,
) -> np.ndarray:
    """Build embeddings using the configured semantic mode."""
    if len(chunks) == 0:
        raise ValueError("chunks cannot be empty")
    if embedding_mode == "text":
        return _embedding_utils.embed_texts(
            texts=[chunk.text for chunk in chunks],
            model_name=embedding_model,
            batch_size=batch_size,
        )
    if embedding_mode != "image_text_combo":
        raise ValueError(f"Unsupported embedding_mode: {embedding_mode}")
    if image_text_weight is None:
        raise ValueError("image_text_weight is required for embedding_mode 'image_text_combo'")

    text_embeddings = _embedding_utils.embed_clip_texts(
        texts=[chunk.text for chunk in chunks],
        model_name=embedding_model,
        batch_size=batch_size,
    )

    if source_image_path is not None:
        image_embedding = _embedding_utils.embed_clip_images(
            image_paths=[source_image_path],
            model_name=embedding_model,
            batch_size=1,
        )[0]
        image_embeddings = np.repeat(image_embedding[np.newaxis, :], len(chunks), axis=0)
        return _embedding_utils.combine_modal_embeddings(image_embeddings, text_embeddings, image_text_weight)

    unique_paths: list[Path] = []
    path_to_index: dict[str, int] = {}
    for chunk in chunks:
        path = URI.from_any(chunk.uri).path
        path_key = str(path)
        if path_key not in path_to_index:
            path_to_index[path_key] = len(unique_paths)
            unique_paths.append(path)

    unique_image_embeddings = _embedding_utils.embed_clip_images(
        image_paths=unique_paths,
        model_name=embedding_model,
        batch_size=batch_size,
    )
    image_embeddings = np.asarray(
        [unique_image_embeddings[path_to_index[str(URI.from_any(chunk.uri).path)]] for chunk in chunks],
        dtype=np.float32,
    )
    return _embedding_utils.combine_modal_embeddings(image_embeddings, text_embeddings, image_text_weight)
