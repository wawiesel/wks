"""Build embeddings for a named index."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import IndexEmbedOutput


def cmd_embed(
    name: str = "",
    batch_size: int = 64,
) -> StageResult:
    """Build embeddings for all chunks in an index."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        if batch_size <= 0:
            yield (1.0, "Complete")
            result_obj.result = "Invalid batch size"
            result_obj.output = IndexEmbedOutput(
                errors=[f"batch_size must be > 0 (found: {batch_size})"],
                warnings=[],
                index_name="",
                embedding_model="",
                chunk_count=0,
                dimensions=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "Index not configured"
            result_obj.output = IndexEmbedOutput(
                errors=["No index section in config"],
                warnings=[],
                index_name="",
                embedding_model="",
                chunk_count=0,
                dimensions=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        index_name = name if name else config.index.default_index
        if index_name not in config.index.indexes:
            yield (1.0, "Complete")
            result_obj.result = f"Unknown index: {index_name}"
            result_obj.output = IndexEmbedOutput(
                errors=[f"Index '{index_name}' not defined in config (available: {list(config.index.indexes.keys())})"],
                warnings=[],
                index_name=index_name,
                embedding_model="",
                chunk_count=0,
                dimensions=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return
        spec = config.index.indexes[index_name]
        embedding_model = spec.embedding_model
        if embedding_model is None:
            yield (1.0, "Complete")
            result_obj.result = f"Index '{index_name}' has no embedding_model"
            result_obj.output = IndexEmbedOutput(
                errors=[
                    f"Index '{index_name}' has no embedding_model configured. "
                    "Set index.indexes.<name>.embedding_model in config."
                ],
                warnings=[],
                index_name=index_name,
                embedding_model="",
                chunk_count=0,
                dimensions=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.25, "Loading chunks...")
        from ._ChunkStore import _ChunkStore

        with Database(config.database, "index") as db:
            chunks = _ChunkStore(db).get_all(index_name)

        if not chunks:
            yield (1.0, "Complete")
            result_obj.result = f"Index '{index_name}' is empty"
            result_obj.output = IndexEmbedOutput(
                errors=[f"Index '{index_name}' is empty"],
                warnings=[],
                index_name=index_name,
                embedding_model=embedding_model,
                chunk_count=0,
                dimensions=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.45, f"Embedding {len(chunks)} chunks...")
        from ._embedding_utils import embed_texts

        texts = [chunk.text for chunk in chunks]
        embeddings = embed_texts(texts=texts, model_name=embedding_model, batch_size=batch_size)

        yield (0.8, "Storing embeddings...")
        from ._EmbeddingStore import _EmbeddingStore

        docs = [
            {
                "index_name": index_name,
                "embedding_model": embedding_model,
                "uri": chunk.uri,
                "chunk_index": chunk.chunk_index,
                "tokens": chunk.tokens,
                "text": chunk.text,
                "embedding": embeddings[i].tolist(),
            }
            for i, chunk in enumerate(chunks)
        ]

        with Database(config.database, "index_embeddings") as db:
            _EmbeddingStore(db).replace_index_model(index_name=index_name, embedding_model=embedding_model, docs=docs)

        yield (1.0, "Complete")
        result_obj.result = f"Embedded index '{index_name}' ({len(chunks)} chunks)"
        result_obj.output = IndexEmbedOutput(
            errors=[],
            warnings=[],
            index_name=index_name,
            embedding_model=embedding_model,
            chunk_count=len(chunks),
            dimensions=int(embeddings.shape[1]),
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Building embeddings for index '{name or '(default)'}'...",
        progress_callback=do_work,
    )
