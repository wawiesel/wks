"""Search command for lexical BM25 and semantic embedding search."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import SearchOutput
from ._dedupe_hits import _dedupe_hits


def cmd(
    query: str = "",
    index: str = "",
    k: int = 10,
    query_image: str = "",
) -> StageResult:
    """Search a named index using its configured search mode."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "Index not configured"
            result_obj.output = SearchOutput(
                errors=["No index section in config"],
                warnings=[],
                query=query,
                index_name="",
                search_mode="lexical",
                embedding_model=None,
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        index_name = index if index else config.index.default_index
        if index_name not in config.index.indexes:
            yield (1.0, "Complete")
            result_obj.result = f"Unknown index: {index_name}"
            result_obj.output = SearchOutput(
                errors=[f"Index '{index_name}' not defined in config (available: {list(config.index.indexes.keys())})"],
                warnings=[],
                query=query,
                index_name=index_name,
                search_mode="lexical",
                embedding_model=None,
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return
        spec = config.index.indexes[index_name]
        embedding_model = spec.embedding_model
        embedding_mode = spec.embedding_mode
        search_mode = "semantic" if embedding_model is not None else "lexical"
        query_output = query if query.strip() else query_image

        if embedding_model is not None:
            import numpy as np

            from ..index._embedding_utils import cosine_scores
            from ..index._EmbeddingStore import _EmbeddingStore
            from ._build_query_embedding import build_query_embedding

            with Database(config.database, "index_embeddings") as db:
                yield (0.3, "Loading embeddings...")
                docs = _EmbeddingStore(db).get_all(index_name=index_name, embedding_model=embedding_model)

            if not docs:
                yield (1.0, "Complete")
                result_obj.result = f"No embeddings for index '{index_name}'"
                result_obj.output = SearchOutput(
                    errors=[
                        f"No embeddings found for index '{index_name}' and model '{embedding_model}'. "
                        "Run: wksc index embed <index_name>"
                    ],
                    warnings=[],
                    query=query_output,
                    index_name=index_name,
                    search_mode=search_mode,
                    embedding_model=embedding_model,
                    hits=[],
                    total_chunks=0,
                ).model_dump(mode="python")
                result_obj.success = False
                return

            yield (0.55, f"Embedding query with {embedding_model}...")
            try:
                query_embedding = build_query_embedding(
                    query=query,
                    query_image=query_image,
                    embedding_model=embedding_model,
                    embedding_mode=embedding_mode,
                    image_text_weight=spec.image_text_weight,
                )
            except Exception as exc:
                yield (1.0, "Complete")
                result_obj.result = str(exc)
                result_obj.output = SearchOutput(
                    errors=[str(exc)],
                    warnings=[],
                    query=query_output,
                    index_name=index_name,
                    search_mode=search_mode,
                    embedding_model=embedding_model,
                    hits=[],
                    total_chunks=len(docs),
                ).model_dump(mode="python")
                result_obj.success = False
                return

            yield (0.7, "Scoring chunks...")
            matrix = np.asarray([doc["embedding"] for doc in docs], dtype=np.float32)
            scores = cosine_scores(query_embedding, matrix)
            ranked = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)
            ranked_hits = [
                {
                    "uri": docs[i]["uri"],
                    "chunk_index": docs[i]["chunk_index"],
                    "score": round(float(scores[i]), 4),
                    "tokens": docs[i]["tokens"],
                    "text": docs[i]["text"],
                }
                for i in ranked
            ]
            hits = _dedupe_hits(ranked_hits, k)

            yield (1.0, "Complete")
            result_obj.result = f"Found {len(hits)} results for '{query_output}'"
            result_obj.output = SearchOutput(
                errors=[],
                warnings=[],
                query=query_output,
                index_name=index_name,
                search_mode=search_mode,
                embedding_model=embedding_model,
                hits=hits,
                total_chunks=len(docs),
            ).model_dump(mode="python")
            result_obj.success = True
            return

        from ..index._ChunkStore import _ChunkStore

        if query_image.strip():
            yield (1.0, "Complete")
            result_obj.result = "query_image is only supported for semantic indexes"
            result_obj.output = SearchOutput(
                errors=["query_image requires an index configured with embedding_model"],
                warnings=[],
                query=query_output,
                index_name=index_name,
                search_mode=search_mode,
                embedding_model=embedding_model,
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return
        if not query.strip():
            yield (1.0, "Complete")
            result_obj.result = "Found 0 results for ''"
            result_obj.output = SearchOutput(
                errors=[],
                warnings=[],
                query=query_output,
                index_name=index_name,
                search_mode=search_mode,
                embedding_model=embedding_model,
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = True
            return

        with Database(config.database, "index") as db:
            store = _ChunkStore(db)

            yield (0.3, "Loading chunks...")
            chunks = store.get_all(index_name)

            if not chunks:
                yield (1.0, "Complete")
                result_obj.result = f"Index '{index_name}' is empty"
                result_obj.output = SearchOutput(
                    errors=[f"Index '{index_name}' is empty"],
                    warnings=[],
                    query=query_output,
                    index_name=index_name,
                    search_mode=search_mode,
                    embedding_model=embedding_model,
                    hits=[],
                    total_chunks=0,
                ).model_dump(mode="python")
                result_obj.success = False
                return

            yield (0.5, "Building search index...")
            from rank_bm25 import BM25Okapi

            corpus = [chunk.text.lower().split() for chunk in chunks]
            bm25 = BM25Okapi(corpus)

            yield (0.7, f"Searching for: {query}...")
            query_terms = set(query.lower().split())
            scores = bm25.get_scores(list(query_terms))

            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            ranked_hits = [
                {
                    "uri": chunks[i].uri,
                    "chunk_index": chunks[i].chunk_index,
                    "score": round(float(scores[i]), 4),
                    "tokens": chunks[i].tokens,
                    "text": chunks[i].text,
                }
                for i in ranked
                if query_terms.intersection(corpus[i])
            ]
            hits = _dedupe_hits(ranked_hits, k)

            yield (1.0, "Complete")
            result_obj.result = f"Found {len(hits)} results for '{query_output}'"
            result_obj.output = SearchOutput(
                errors=[],
                warnings=[],
                query=query_output,
                index_name=index_name,
                search_mode=search_mode,
                embedding_model=embedding_model,
                hits=hits,
                total_chunks=len(chunks),
            ).model_dump(mode="python")
            result_obj.success = True

    return StageResult(
        announce=f"Searching for '{query if query.strip() else query_image}'...",
        progress_callback=do_work,
    )
