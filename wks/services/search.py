from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wks.api.config.WKSConfig import WKSConfig
from wks.api.index._IndexSpec import _IndexSpec
from wks.api.search._dedupe_hits import _dedupe_hits
from wks.api.search._rrf import rrf_merge
from wks.api.search._SearchRuntime import _SEARCH_RUNTIME, _LexicalIndexState, _SemanticIndexState

from ._models import FailureKind, ServiceResponse


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    index: str = ""
    k: int = Field(default=10, ge=1)
    query_image: str = ""
    strategy: str = ""


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    chunk_index: int
    score: float
    tokens: int
    text: str


class SearchResponse(ServiceResponse):
    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    query: str
    index_name: str
    search_mode: Literal["lexical", "semantic", "combined"]
    embedding_model: str | None = None
    hits: list[SearchHit] = Field(default_factory=list)
    total_chunks: int = 0


def search_documents(request: SearchRequest, *, config: WKSConfig | None = None) -> SearchResponse:
    loaded_config = config or _SEARCH_RUNTIME.load_config()
    if loaded_config.index is None:
        return _error_response(
            message="Index not configured",
            failure_kind="config",
            errors=["No index section in config"],
            query=request.query,
            index_name="",
            search_mode="lexical",
        )
    if not request.query.strip() and not request.query_image.strip():
        return _error_response(
            message="Either query or query_image is required",
            failure_kind="validation",
            errors=["Either query or query_image is required"],
            query="",
            index_name="",
            search_mode="lexical",
        )
    if request.index and request.strategy:
        return _error_response(
            message="Cannot specify both --index and --strategy",
            failure_kind="validation",
            errors=["Cannot specify both --index and --strategy"],
            query=request.query,
            index_name="",
            search_mode="lexical",
        )

    strategy_name = _resolve_strategy_name(loaded_config, request)
    if strategy_name:
        return _run_strategy_search(loaded_config, request, strategy_name)
    return _run_single_index_search(loaded_config, request)


def _resolve_strategy_name(config: WKSConfig, request: SearchRequest) -> str:
    assert config.index is not None
    if request.strategy:
        return request.strategy
    if not request.index and config.index.default_strategy:
        return config.index.default_strategy
    return ""


def _run_single_index_search(config: WKSConfig, request: SearchRequest) -> SearchResponse:
    assert config.index is not None
    index_name = request.index if request.index else config.index.default_index
    if index_name not in config.index.indexes:
        available = list(config.index.indexes.keys())
        return _error_response(
            message=f"Unknown index: {index_name}",
            failure_kind="not_found",
            errors=[f"Index '{index_name}' not defined in config (available: {available})"],
            query=_query_output(request),
            index_name=index_name,
            search_mode="lexical",
        )

    spec = config.index.indexes[index_name]
    if spec.embedding_model is not None:
        return _run_semantic_search(config, request, index_name, spec)
    return _run_lexical_search(config, request, index_name)


def _run_semantic_search(
    config: WKSConfig,
    request: SearchRequest,
    index_name: str,
    spec: _IndexSpec,
) -> SearchResponse:
    embedding_model = spec.embedding_model
    assert embedding_model is not None
    semantic_state = _SEARCH_RUNTIME.get_semantic_index_state(config, index_name, embedding_model)
    if not semantic_state.docs:
        return _error_response(
            message=f"No embeddings for index '{index_name}'",
            failure_kind="not_found",
            errors=[
                f"No embeddings found for index '{index_name}' and model '{embedding_model}'. "
                "Run: wksc index embed <index_name>"
            ],
            query=_query_output(request),
            index_name=index_name,
            search_mode="semantic",
            embedding_model=embedding_model,
            total_chunks=0,
        )

    try:
        hits = _rank_semantic_hits(semantic_state, spec, request.query, request.query_image, request.k)
    except Exception as exc:
        return _error_response(
            message=str(exc),
            failure_kind="runtime",
            errors=[str(exc)],
            query=_query_output(request),
            index_name=index_name,
            search_mode="semantic",
            embedding_model=embedding_model,
            total_chunks=len(semantic_state.docs),
        )

    return SearchResponse(
        success=True,
        message=f"Found {len(hits)} results for '{_query_output(request)}'",
        errors=[],
        warnings=[],
        query=_query_output(request),
        index_name=index_name,
        search_mode="semantic",
        embedding_model=embedding_model,
        hits=[SearchHit(**hit) for hit in hits],
        total_chunks=len(semantic_state.docs),
    )


def _run_lexical_search(config: WKSConfig, request: SearchRequest, index_name: str) -> SearchResponse:
    if request.query_image.strip():
        return _error_response(
            message="query_image is only supported for semantic indexes",
            failure_kind="validation",
            errors=["query_image requires an index configured with embedding_model"],
            query=_query_output(request),
            index_name=index_name,
            search_mode="lexical",
        )
    if not request.query.strip():
        return SearchResponse(
            success=True,
            message="Found 0 results for ''",
            errors=[],
            warnings=[],
            query="",
            index_name=index_name,
            search_mode="lexical",
            embedding_model=None,
            hits=[],
            total_chunks=0,
        )

    lexical_state = _SEARCH_RUNTIME.get_lexical_index_state(config, index_name)
    if not lexical_state.chunks:
        return _error_response(
            message=f"Index '{index_name}' is empty",
            failure_kind="not_found",
            errors=[f"Index '{index_name}' is empty"],
            query=request.query,
            index_name=index_name,
            search_mode="lexical",
        )

    hits = _rank_lexical_hits(lexical_state, request.query, request.k)
    return SearchResponse(
        success=True,
        message=f"Found {len(hits)} results for '{request.query}'",
        errors=[],
        warnings=[],
        query=request.query,
        index_name=index_name,
        search_mode="lexical",
        embedding_model=None,
        hits=[SearchHit(**hit) for hit in hits],
        total_chunks=len(lexical_state.chunks),
    )


def _run_strategy_search(config: WKSConfig, request: SearchRequest, strategy_name: str) -> SearchResponse:
    assert config.index is not None
    if strategy_name not in config.index.strategies:
        available = list(config.index.strategies.keys())
        return _error_response(
            message=f"Unknown strategy: {strategy_name}",
            failure_kind="not_found",
            errors=[f"Strategy '{strategy_name}' not defined in config (available: {available})"],
            query=_query_output(request),
            index_name=strategy_name,
            search_mode="combined",
        )

    strategy = config.index.strategies[strategy_name]
    over_fetch = request.k * 3
    ranked_lists: list[list[dict[str, Any]]] = []
    warnings: list[str] = []
    total_chunks = 0

    for index_name in strategy.indexes:
        if index_name not in config.index.indexes:
            warnings.append(f"Strategy index '{index_name}' not found, skipping")
            continue
        spec = config.index.indexes[index_name]
        if spec.embedding_model is not None:
            semantic_response = _run_semantic_search(
                config,
                SearchRequest(
                    query=request.query,
                    index=index_name,
                    k=over_fetch,
                    query_image=request.query_image,
                ),
                index_name,
                spec,
            )
            if semantic_response.success:
                ranked_lists.append([hit.model_dump(mode="python") for hit in semantic_response.hits])
                total_chunks += len(semantic_response.hits)
            else:
                warnings.extend(semantic_response.errors)
            continue
        if not request.query.strip():
            continue
        lexical_response = _run_lexical_search(
            config,
            SearchRequest(query=request.query, index=index_name, k=over_fetch),
            index_name,
        )
        if lexical_response.success:
            ranked_lists.append([hit.model_dump(mode="python") for hit in lexical_response.hits])
            total_chunks += len(lexical_response.hits)
        else:
            warnings.extend(lexical_response.errors)

    if not ranked_lists:
        return SearchResponse(
            success=True,
            message=f"No results from any index in strategy '{strategy_name}'",
            errors=[],
            warnings=warnings,
            query=_query_output(request),
            index_name=strategy_name,
            search_mode="combined",
            embedding_model=None,
            hits=[],
            total_chunks=0,
        )

    merged = rrf_merge(ranked_lists, request.k)
    hits = _dedupe_hits(merged, request.k)
    return SearchResponse(
        success=True,
        message=f"Found {len(hits)} results for '{_query_output(request)}'",
        errors=[],
        warnings=warnings,
        query=_query_output(request),
        index_name=strategy_name,
        search_mode="combined",
        embedding_model=None,
        hits=[SearchHit(**hit) for hit in hits],
        total_chunks=total_chunks,
    )


def _rank_semantic_hits(
    state: _SemanticIndexState,
    spec: _IndexSpec,
    query: str,
    query_image: str,
    k: int,
) -> list[dict[str, Any]]:
    from wks.api.index._embedding_utils import cosine_scores
    from wks.api.search._build_query_embedding import build_query_embedding

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

    ranked = sorted(range(len(boosted)), key=lambda item: boosted[item], reverse=True)
    ranked_hits = [
        {
            "uri": state.docs[item]["uri"],
            "chunk_index": state.docs[item]["chunk_index"],
            "score": round(boosted[item], 4),
            "tokens": state.docs[item]["tokens"],
            "text": state.docs[item]["text"],
        }
        for item in ranked
    ]
    return _dedupe_hits(ranked_hits, k)


def _rank_lexical_hits(state: _LexicalIndexState, query: str, k: int) -> list[dict[str, Any]]:
    if state.bm25 is None:
        return []
    query_terms = set(query.lower().split())
    scores = state.bm25.get_scores(list(query_terms))
    ranked = sorted(range(len(scores)), key=lambda item: scores[item], reverse=True)
    ranked_hits = [
        {
            "uri": state.chunks[item].uri,
            "chunk_index": state.chunks[item].chunk_index,
            "score": round(float(scores[item]), 4),
            "tokens": state.chunks[item].tokens,
            "text": state.chunks[item].text,
        }
        for item in ranked
        if query_terms.intersection(state.corpus[item])
    ]
    return _dedupe_hits(ranked_hits, k)


def _query_output(request: SearchRequest) -> str:
    return request.query if request.query.strip() else request.query_image


def _error_response(
    *,
    message: str,
    failure_kind: FailureKind,
    errors: list[str],
    query: str,
    index_name: str,
    search_mode: Literal["lexical", "semantic", "combined"],
    embedding_model: str | None = None,
    total_chunks: int = 0,
) -> SearchResponse:
    return SearchResponse(
        success=False,
        message=message,
        failure_kind=failure_kind,
        errors=errors,
        warnings=[],
        query=query,
        index_name=index_name,
        search_mode=search_mode,
        embedding_model=embedding_model,
        hits=[],
        total_chunks=total_chunks,
    )
