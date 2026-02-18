"""Search command - BM25 search over an index."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import SearchOutput


def cmd(query: str, index: str = "", k: int = 10) -> StageResult:
    """Search a named index with BM25 ranking."""

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
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        index_name = index if index else config.index.default_index

        from ..index._ChunkStore import _ChunkStore

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
                    query=query,
                    index_name=index_name,
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
            scores = bm25.get_scores(query.lower().split())

            ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            hits = [
                {
                    "uri": chunks[i].uri,
                    "chunk_index": chunks[i].chunk_index,
                    "score": round(float(scores[i]), 4),
                    "tokens": chunks[i].tokens,
                    "text": chunks[i].text,
                }
                for i in ranked[:k]
                if scores[i] > 0
            ]

            yield (1.0, "Complete")
            result_obj.result = f"Found {len(hits)} results for '{query}'"
            result_obj.output = SearchOutput(
                errors=[],
                warnings=[],
                query=query,
                index_name=index_name,
                hits=hits,
                total_chunks=len(chunks),
            ).model_dump(mode="python")
            result_obj.success = True

    return StageResult(
        announce=f"Searching for '{query}'...",
        progress_callback=do_work,
    )
