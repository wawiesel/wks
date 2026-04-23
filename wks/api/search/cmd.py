"""Search command for lexical BM25 and semantic embedding search."""

from collections.abc import Iterator
from typing import Any

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..index._IndexSpec import _IndexSpec
from . import SearchOutput
from ._dedupe_hits import _dedupe_hits
from ._rrf import rrf_merge
from ._SearchRuntime import _SEARCH_RUNTIME, _LexicalIndexState, _SemanticIndexState


def _rank_semantic_hits(
    state: _SemanticIndexState,
    spec: _IndexSpec,
    query: str,
    query_image: str,
    k: int,
) -> list[dict[str, Any]]:
    """Rank semantic hits using the hot runtime state."""
    from ..index._embedding_utils import cosine_scores
    from ._build_query_embedding import build_query_embedding

    if not state.docs:
        return []

    embedding_model = spec.embedding_model
    assert embedding_model is not None

    query_embedding = build_query_embedding(
        query=query,
        query_image=query_image,
        embedding_model=embedding_model,
        embedding_mode=spec.embedding_mode,
        image_text_weight=spec.image_text_weight,
    )

    scores = cosine_scores(query_embedding, state.matrix)
    query_terms = {term.lower() for term in query.split() if term} if query.strip() else set()
    boosted: list[float] = []
    for index, segments in enumerate(state.path_segments):
        if not query_terms or not segments:
            boosted.append(float(scores[index]))
            continue
        matches = sum(1 for term in query_terms if term in segments)
        boosted.append(float(scores[index]) * (1.0 + 0.2 * matches))

    ranked = sorted(range(len(boosted)), key=lambda i: boosted[i], reverse=True)
    ranked_hits = [
        {
            "uri": state.docs[i]["uri"],
            "chunk_index": state.docs[i]["chunk_index"],
            "score": round(boosted[i], 4),
            "tokens": state.docs[i]["tokens"],
            "text": state.docs[i]["text"],
        }
        for i in ranked
    ]
    return _dedupe_hits(ranked_hits, k)


def _rank_lexical_hits(state: _LexicalIndexState, query: str, k: int) -> list[dict[str, Any]]:
    """Rank lexical hits using the hot runtime state."""
    if state.bm25 is None:
        return []

    query_terms = set(query.lower().split())
    scores = state.bm25.get_scores(list(query_terms))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranked_hits = [
        {
            "uri": state.chunks[i].uri,
            "chunk_index": state.chunks[i].chunk_index,
            "score": round(float(scores[i]), 4),
            "tokens": state.chunks[i].tokens,
            "text": state.chunks[i].text,
        }
        for i in ranked
        if query_terms.intersection(state.corpus[i])
    ]
    return _dedupe_hits(ranked_hits, k)


def _search_semantic(
    config: WKSConfig,
    index_name: str,
    spec: _IndexSpec,
    query: str,
    query_image: str,
    k: int,
) -> list[dict[str, Any]]:
    """Run semantic search on a single index, return ranked hits."""
    embedding_model = spec.embedding_model
    assert embedding_model is not None

    state = _SEARCH_RUNTIME.get_semantic_index_state(config, index_name, embedding_model)
    return _rank_semantic_hits(state, spec, query, query_image, k)


def _search_lexical(
    config: WKSConfig,
    index_name: str,
    query: str,
    k: int,
) -> list[dict[str, Any]]:
    """Run BM25 lexical search on a single index, return ranked hits."""
    state = _SEARCH_RUNTIME.get_lexical_index_state(config, index_name)
    return _rank_lexical_hits(state, query, k)


def cmd(
    query: str = "",
    index: str = "",
    k: int = 10,
    query_image: str = "",
    strategy: str = "",
) -> StageResult:
    """Search a named index using its configured search mode."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = _SEARCH_RUNTIME.load_config()

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

        if not query.strip() and not query_image.strip():
            yield (1.0, "Complete")
            result_obj.result = "Either query or query_image is required"
            result_obj.output = SearchOutput(
                errors=["Either query or query_image is required"],
                warnings=[],
                query="",
                index_name="",
                search_mode="lexical",
                embedding_model=None,
                hits=[],
                total_chunks=0,
            ).model_dump(mode="python")
            result_obj.success = False
            return

        # Resolve: --index and --strategy are mutually exclusive
        if index and strategy:
            yield (1.0, "Complete")
            result_obj.result = "Cannot specify both --index and --strategy"
            result_obj.output = SearchOutput(
                errors=["Cannot specify both --index and --strategy"],
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

        # Determine what to do: strategy search or single-index search
        strategy_name = ""
        if strategy:
            strategy_name = strategy
        elif not index and config.index.default_strategy:
            strategy_name = config.index.default_strategy

        if strategy_name:
            # Strategy search path
            yield from _strategy_search(result_obj, config, strategy_name, query, query_image, k)
            return

        # Single-index search path (original behavior)
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
        search_mode = "semantic" if embedding_model is not None else "lexical"
        query_output = query if query.strip() else query_image

        if embedding_model is not None:
            yield (0.3, "Loading semantic index...")
            semantic_state = _SEARCH_RUNTIME.get_semantic_index_state(config, index_name, embedding_model)

            if not semantic_state.docs:
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
                hits = _rank_semantic_hits(semantic_state, spec, query, query_image, k)
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
                    total_chunks=len(semantic_state.docs),
                ).model_dump(mode="python")
                result_obj.success = False
                return

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
                total_chunks=len(semantic_state.docs),
            ).model_dump(mode="python")
            result_obj.success = True
            return

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

        yield (0.3, "Loading lexical index...")
        lexical_state = _SEARCH_RUNTIME.get_lexical_index_state(config, index_name)

        if not lexical_state.chunks:
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

        yield (0.7, f"Searching for: {query}...")
        hits = _rank_lexical_hits(lexical_state, query, k)

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
            total_chunks=len(lexical_state.chunks),
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Searching for '{query if query.strip() else query_image}'...",
        progress_callback=do_work,
    )


def _strategy_search(
    result_obj: StageResult,
    config: WKSConfig,
    strategy_name: str,
    query: str,
    query_image: str,
    k: int,
) -> Iterator[tuple[float, str]]:
    """Execute a strategy search: query multiple indexes and merge with RRF."""
    assert config.index is not None
    query_output = query if query.strip() else query_image

    if strategy_name not in config.index.strategies:
        yield (1.0, "Complete")
        result_obj.result = f"Unknown strategy: {strategy_name}"
        result_obj.output = SearchOutput(
            errors=[
                f"Strategy '{strategy_name}' not defined in config (available: {list(config.index.strategies.keys())})"
            ],
            warnings=[],
            query=query_output,
            index_name=strategy_name,
            search_mode="combined",
            embedding_model=None,
            hits=[],
            total_chunks=0,
        ).model_dump(mode="python")
        result_obj.success = False
        return

    strategy = config.index.strategies[strategy_name]
    over_fetch = k * 3

    yield (0.3, f"Querying {len(strategy.indexes)} indexes...")

    ranked_lists: list[list[dict]] = []
    warnings: list[str] = []
    total_chunks = 0

    for idx_name in strategy.indexes:
        if idx_name not in config.index.indexes:
            warnings.append(f"Strategy index '{idx_name}' not found, skipping")
            continue
        spec = config.index.indexes[idx_name]

        if spec.embedding_model is not None:
            try:
                hits = _search_semantic(config, idx_name, spec, query, query_image, over_fetch)
                ranked_lists.append(hits)
                total_chunks += len(hits)
            except Exception as exc:
                warnings.append(f"Semantic search on '{idx_name}' failed: {exc}")
        else:
            if not query.strip():
                continue
            hits = _search_lexical(config, idx_name, query, over_fetch)
            ranked_lists.append(hits)
            total_chunks += len(hits)

    if not ranked_lists:
        yield (1.0, "Complete")
        result_obj.result = f"No results from any index in strategy '{strategy_name}'"
        result_obj.output = SearchOutput(
            errors=[],
            warnings=warnings,
            query=query_output,
            index_name=strategy_name,
            search_mode="combined",
            embedding_model=None,
            hits=[],
            total_chunks=0,
        ).model_dump(mode="python")
        result_obj.success = True
        return

    yield (0.7, "Merging results with RRF...")
    merged = rrf_merge(ranked_lists, k)
    hits = _dedupe_hits(merged, k)

    yield (1.0, "Complete")
    result_obj.result = f"Found {len(hits)} results for '{query_output}'"
    result_obj.output = SearchOutput(
        errors=[],
        warnings=warnings,
        query=query_output,
        index_name=strategy_name,
        search_mode="combined",
        embedding_model=None,
        hits=hits,
        total_chunks=total_chunks,
    ).model_dump(mode="python")
    result_obj.success = True
