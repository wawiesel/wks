"""Prototype document-similarity command built from chunk similarity."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from ..config._progress_heartbeat import call_with_heartbeat, relay_stage_with_heartbeat
from ..config.StageResult import StageResult
from ..config.URI import URI
from ..config.WKSConfig import WKSConfig
from ..index._build_semantic_embeddings import build_semantic_embeddings
from ..index._embedding_utils import cosine_scores
from ..index._IndexSpec import _IndexSpec
from ..index._SlidingWindowChunker import _SlidingWindowChunker
from ..search._SearchRuntime import _SEARCH_RUNTIME, _SemanticIndexState
from ..transform.cmd_engine import cmd_engine
from ..transform.get_content import get_content
from . import SimilarOutput
from .SimilarConfig import SimilarConfig


@dataclass(frozen=True, slots=True)
class _QueryDoc:
    """Normalized query document ready for semantic comparison."""

    uri: str
    path: Path
    chunks: list[Any]
    embeddings: np.ndarray
    checksum: str
    path_segments: frozenset[str]


@dataclass(frozen=True, slots=True)
class _CandidateMetrics:
    """Document-level similarity features for one candidate URI."""

    uri: str
    label: str
    score: float
    matched_chunks: int
    coverage_query: float
    coverage_candidate: float
    mean_similarity: float
    max_similarity: float
    order_consistency: float
    stem_similarity: float
    path_similarity: float
    evidence: list[dict[str, Any]]


def _canonical_uri(value: str) -> str:
    """Return a canonical URI string for grouping and display."""
    return str(URI.from_any(value))


def _path_segments(uri: str) -> frozenset[str]:
    """Return lowercase path segments and stem for simple path similarity."""
    try:
        path = URI.from_any(uri).path
    except Exception:
        return frozenset()
    parts = {part.lower() for part in path.parts}
    parts.add(path.stem.lower())
    return frozenset(parts)


def _file_checksum(path: Path) -> str | None:
    """Return SHA-256 for a real file, or None when unavailable."""
    try:
        if not path.is_file():
            return None
        return sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _preview(text: str, limit: int) -> str:
    """Compress whitespace and trim long evidence snippets."""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _resolve_semantic_index(
    config: WKSConfig,
    similar_config: SimilarConfig,
    requested_index: str | None,
) -> tuple[str, _IndexSpec] | tuple[None, None]:
    """Resolve one configured semantic text index."""
    if config.index is None:
        return None, None

    selected_index = requested_index or similar_config.default_index or ""

    if selected_index:
        spec = config.index.indexes.get(selected_index)
        if spec is None or spec.embedding_model is None:
            return None, None
        return selected_index, spec

    if "semantic" in config.index.indexes:
        spec = config.index.indexes["semantic"]
        if spec.embedding_model is not None:
            return "semantic", spec

    default_name = config.index.default_index
    if default_name:
        default_spec = config.index.indexes.get(default_name)
        if default_spec is not None and default_spec.embedding_model is not None:
            return default_name, default_spec

    for name, spec in config.index.indexes.items():
        if spec.embedding_model is not None:
            return name, spec
    return None, None


def _group_candidate_rows(state: _SemanticIndexState) -> dict[str, list[int]]:
    """Group embedding-row indices by canonical candidate URI."""
    grouped: dict[str, list[int]] = defaultdict(list)
    for idx, doc in enumerate(state.docs):
        grouped[_canonical_uri(doc["uri"])].append(idx)
    return dict(grouped)


def _collect_candidate_scores(
    query_doc: _QueryDoc,
    state: _SemanticIndexState,
    *,
    per_chunk: int,
    rrf_k: float,
) -> dict[str, float]:
    """Collect candidate URIs with a small RRF-style seed score."""
    scores: dict[str, float] = defaultdict(float)
    if len(state.docs) == 0:
        return {}

    for query_embedding in query_doc.embeddings:
        ranked = np.argsort(-cosine_scores(query_embedding, state.matrix))
        seen_uris: set[str] = set()
        rank = 0
        for idx in ranked.tolist():
            raw_score = float(state.matrix[idx] @ query_embedding)
            if raw_score <= 0.0:
                continue
            uri = _canonical_uri(state.docs[idx]["uri"])
            if uri == query_doc.uri or uri in seen_uris:
                continue
            seen_uris.add(uri)
            rank += 1
            scores[uri] += 1.0 / (rrf_k + rank)
            if rank >= per_chunk:
                break
    return dict(scores)


def _greedy_matches(similarity: np.ndarray, match_threshold: float) -> list[tuple[int, int, float]]:
    """Greedily match query chunks to candidate chunks above threshold."""
    if similarity.ndim != 2:
        raise ValueError(f"similarity matrix must be 2D (found ndim={similarity.ndim})")
    pairs: list[tuple[float, int, int]] = []
    rows, cols = similarity.shape
    for i in range(rows):
        for j in range(cols):
            score = float(similarity[i, j])
            if score >= match_threshold:
                pairs.append((score, i, j))
    pairs.sort(key=lambda item: item[0], reverse=True)

    used_query: set[int] = set()
    used_candidate: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for score, query_idx, candidate_idx in pairs:
        if query_idx in used_query or candidate_idx in used_candidate:
            continue
        used_query.add(query_idx)
        used_candidate.add(candidate_idx)
        matches.append((query_idx, candidate_idx, score))
    return matches


def _order_consistency(matches: list[tuple[int, int, float]], candidate_docs: list[dict[str, Any]]) -> float:
    """Return a simple monotonic-order score for matched chunks."""
    if len(matches) == 0:
        return 0.0
    if len(matches) == 1:
        return 1.0
    ordered = sorted(matches, key=lambda item: item[0])
    candidate_positions = [int(candidate_docs[candidate_idx]["chunk_index"]) for _, candidate_idx, _ in ordered]
    increases = sum(1 for left, right in pairwise(candidate_positions) if right >= left)
    return increases / float(len(candidate_positions) - 1)


def _stem_similarity(query_uri: str, candidate_uri: str) -> float:
    """Return normalized filename-stem similarity."""
    query_stem = URI.from_any(query_uri).path.stem.lower()
    candidate_stem = URI.from_any(candidate_uri).path.stem.lower()
    return float(SequenceMatcher(a=query_stem, b=candidate_stem).ratio())


def _path_similarity(query_segments: frozenset[str], candidate_uri: str) -> float:
    """Return Jaccard similarity on lowercase path segments."""
    candidate_segments = _path_segments(candidate_uri)
    if not query_segments or not candidate_segments:
        return 0.0
    intersection = len(query_segments.intersection(candidate_segments))
    union = len(query_segments.union(candidate_segments))
    if union == 0:
        return 0.0
    return intersection / float(union)


def _probable_export_pair(
    query_uri: str,
    candidate_uri: str,
    stem_similarity: float,
    similar_config: SimilarConfig,
) -> bool:
    """Return True for common source/export relationships."""
    query_suffix = URI.from_any(query_uri).path.suffix.lower()
    candidate_suffix = URI.from_any(candidate_uri).path.suffix.lower()
    export_pairs = {frozenset({left.lower(), right.lower()}) for left, right in similar_config.export_pairs}
    return (
        stem_similarity >= similar_config.same_document_family.export_pair_min_stem_similarity
        and frozenset({query_suffix, candidate_suffix}) in export_pairs
    )


def _label_candidate(
    *,
    query_doc: _QueryDoc,
    candidate_uri: str,
    coverage_query: float,
    coverage_candidate: float,
    mean_similarity: float,
    max_similarity: float,
    order_consistency: float,
    stem_similarity: float,
    path_similarity: float,
    candidate_checksum: str | None,
    matched_chunks: int,
    similar_config: SimilarConfig,
) -> str | None:
    """Assign one practical document-similarity label."""
    if candidate_checksum is not None and candidate_checksum == query_doc.checksum:
        return "exact_duplicate"

    near = similar_config.near_duplicate
    if (
        matched_chunks >= near.min_matched_chunks
        and coverage_query >= near.min_coverage_query
        and coverage_candidate >= near.min_coverage_candidate
        and mean_similarity >= near.min_mean_similarity
        and order_consistency >= near.min_order_consistency
    ):
        return "near_duplicate"

    family = similar_config.same_document_family
    lineage_signal = (
        stem_similarity >= family.min_stem_similarity
        or _probable_export_pair(query_doc.uri, candidate_uri, stem_similarity, similar_config)
        or (
            stem_similarity >= family.support_min_stem_similarity
            and path_similarity >= family.support_min_path_similarity
        )
    )
    if lineage_signal and coverage_query >= family.min_coverage_query and max_similarity >= family.min_max_similarity:
        return "same_document_family"

    topic = similar_config.topic_related
    if (
        matched_chunks >= topic.min_matched_chunks
        and coverage_query >= topic.min_coverage_query
        and (mean_similarity >= topic.min_mean_similarity or max_similarity >= topic.min_max_similarity)
    ):
        return "topic_related"
    return None


def _final_score(
    *,
    label: str,
    initial_score: float,
    mean_similarity: float,
    coverage_query: float,
    coverage_candidate: float,
    order_consistency: float,
    stem_similarity: float,
    path_similarity: float,
    similar_config: SimilarConfig,
) -> float:
    """Blend semantic evidence and lightweight metadata for ranking."""
    if label == "exact_duplicate":
        return 1.0
    weights = similar_config.score_weights
    seed = min(initial_score * weights.seed_scale, 1.0)
    return min(
        weights.mean_similarity * mean_similarity
        + weights.coverage_query * coverage_query
        + weights.coverage_candidate * coverage_candidate
        + weights.order_consistency * order_consistency
        + weights.stem_similarity * stem_similarity
        + weights.path_similarity * path_similarity
        + weights.seed_score * seed,
        0.9999,
    )


def _candidate_metrics(
    *,
    query_doc: _QueryDoc,
    candidate_uri: str,
    candidate_docs: list[dict[str, Any]],
    candidate_matrix: np.ndarray,
    initial_score: float,
    match_threshold: float,
    similar_config: SimilarConfig,
) -> _CandidateMetrics | None:
    """Compute document-level similarity metrics for one candidate."""
    similarity = query_doc.embeddings @ candidate_matrix.T
    matches = _greedy_matches(similarity, match_threshold=match_threshold)
    matched_chunks = len(matches)
    coverage_query = matched_chunks / float(len(query_doc.chunks))
    coverage_candidate = matched_chunks / float(len(candidate_docs)) if candidate_docs else 0.0
    mean_similarity = float(np.mean([score for _, _, score in matches])) if matches else 0.0
    max_similarity = max((score for _, _, score in matches), default=0.0)
    order_consistency = _order_consistency(matches, candidate_docs)
    stem_similarity = _stem_similarity(query_doc.uri, candidate_uri)
    path_similarity = _path_similarity(query_doc.path_segments, candidate_uri)

    candidate_checksum = None
    try:
        candidate_checksum = _file_checksum(URI.from_any(candidate_uri).path)
    except Exception:
        candidate_checksum = None

    label = _label_candidate(
        query_doc=query_doc,
        candidate_uri=candidate_uri,
        coverage_query=coverage_query,
        coverage_candidate=coverage_candidate,
        mean_similarity=mean_similarity,
        max_similarity=max_similarity,
        order_consistency=order_consistency,
        stem_similarity=stem_similarity,
        path_similarity=path_similarity,
        candidate_checksum=candidate_checksum,
        matched_chunks=matched_chunks,
        similar_config=similar_config,
    )
    if label is None:
        return None

    evidence = [
        {
            "query_chunk_index": query_idx,
            "candidate_chunk_index": int(candidate_docs[candidate_idx]["chunk_index"]),
            "score": round(score, 4),
            "query_text": _preview(query_doc.chunks[query_idx].text, similar_config.evidence_chars),
            "candidate_text": _preview(str(candidate_docs[candidate_idx]["text"]), similar_config.evidence_chars),
        }
        for query_idx, candidate_idx, score in sorted(matches, key=lambda item: item[2], reverse=True)[
            : similar_config.evidence_limit
        ]
    ]

    score = _final_score(
        label=label,
        initial_score=initial_score,
        mean_similarity=mean_similarity,
        coverage_query=coverage_query,
        coverage_candidate=coverage_candidate,
        order_consistency=order_consistency,
        stem_similarity=stem_similarity,
        path_similarity=path_similarity,
        similar_config=similar_config,
    )
    return _CandidateMetrics(
        uri=candidate_uri,
        label=label,
        score=round(score, 4),
        matched_chunks=matched_chunks,
        coverage_query=round(coverage_query, 4),
        coverage_candidate=round(coverage_candidate, 4),
        mean_similarity=round(mean_similarity, 4),
        max_similarity=round(max_similarity, 4),
        order_consistency=round(order_consistency, 4),
        stem_similarity=round(stem_similarity, 4),
        path_similarity=round(path_similarity, 4),
        evidence=evidence,
    )


def cmd(
    target: str,
    index: str | None = None,
    top: int | None = None,
    per_chunk: int | None = None,
    candidates: int | None = None,
    match_threshold: float | None = None,
) -> StageResult:
    """Find similar documents for one query file using chunk aggregation."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.05, "Loading configuration...")
        config = _SEARCH_RUNTIME.load_config()
        similar_config = config.similar
        heartbeat_secs = similar_config.heartbeat_secs

        index_name, spec = _resolve_semantic_index(config, similar_config, index)
        if spec is None or index_name is None:
            available = []
            if config.index is not None:
                for name, idx_spec in config.index.indexes.items():
                    if idx_spec.embedding_model is not None:
                        available.append(name)
            yield (1.0, "Complete")
            if config.index is None:
                error = "No index section in config"
            elif index:
                error = f"Index '{index}' is not a configured semantic index"
            else:
                error = "No semantic index is configured"
            result_obj.result = error
            result_obj.output = SimilarOutput(
                errors=[error] if not available else [f"{error} (available semantic indexes: {available})"],
                warnings=[],
                query_uri="",
                index_name=index or "",
                embedding_model=None,
                query_chunk_count=0,
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        if spec.embedding_mode != "text":
            yield (1.0, "Complete")
            error = (
                f"similar currently supports text semantic indexes only "
                f"(index '{index_name}' uses embedding_mode '{spec.embedding_mode}')"
            )
            result_obj.result = error
            result_obj.output = SimilarOutput(
                errors=[error],
                warnings=[],
                query_uri="",
                index_name=index_name,
                embedding_model=spec.embedding_model,
                query_chunk_count=0,
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        try:
            query_path = URI.from_any(target).path
        except ValueError as exc:
            yield (1.0, "Complete")
            result_obj.result = str(exc)
            result_obj.output = SimilarOutput(
                errors=[str(exc)],
                warnings=[],
                query_uri="",
                index_name=index_name,
                embedding_model=spec.embedding_model,
                query_chunk_count=0,
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        if not query_path.exists():
            yield (1.0, "Complete")
            error = f"Query document does not exist: {query_path}"
            result_obj.result = error
            result_obj.output = SimilarOutput(
                errors=[error],
                warnings=[],
                query_uri=str(URI.from_path(query_path)),
                index_name=index_name,
                embedding_model=spec.embedding_model,
                query_chunk_count=0,
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.1, "Resolved query path...")
        try:
            selected_engine = config.transform.default_engine
            transform_result = cmd_engine(selected_engine, URI.from_path(query_path), overrides={}, output=None)
            yield from relay_stage_with_heartbeat(
                transform_result,
                start_progress=0.12,
                end_progress=0.28,
                heartbeat_secs=heartbeat_secs,
                idle_message="Query transform still running",
                prefix="Query transform",
            )
            if not transform_result.success:
                error = transform_result.output.get("errors", [transform_result.result])[0]
                raise ValueError(str(error))

            checksum = str(transform_result.output["checksum"])
            text = yield from call_with_heartbeat(
                lambda: get_content(checksum),
                progress=0.3,
                message="Loading transformed query content from cache...",
                heartbeat_secs=heartbeat_secs,
            )
            if not text.strip():
                raise ValueError(f"Query document has no textual content: {query_path}")

            query_uri = str(URI.from_path(query_path))
            yield (0.34, f"Chunking transformed query text ({len(text):,} chars)...")
            chunker = _SlidingWindowChunker(spec.max_tokens, spec.overlap_tokens)
            chunks = chunker.chunk(text, query_uri)
            if len(chunks) == 0:
                raise ValueError(f"Query document did not produce any chunks: {query_path}")

            embedding_model = spec.embedding_model
            assert embedding_model is not None
            embedding_model_name: str = embedding_model

            def build_query_embeddings() -> np.ndarray:
                return build_semantic_embeddings(
                    chunks=chunks,
                    embedding_model=embedding_model_name,
                    embedding_mode=spec.embedding_mode,
                    image_text_weight=spec.image_text_weight,
                    batch_size=64,
                )

            embeddings = yield from call_with_heartbeat(
                build_query_embeddings,
                progress=0.4,
                message=f"Embedding {len(chunks)} query chunks with {embedding_model}...",
                heartbeat_secs=heartbeat_secs,
            )

            yield (0.48, "Checksumming query document...")
            file_checksum = _file_checksum(query_path)
            if file_checksum is None:
                raise ValueError(f"Could not read query document for checksum: {query_path}")

            query_doc = _QueryDoc(
                uri=query_uri,
                path=query_path,
                chunks=chunks,
                embeddings=embeddings,
                checksum=file_checksum,
                path_segments=_path_segments(query_uri),
            )
        except Exception as exc:
            yield (1.0, "Complete")
            result_obj.result = str(exc)
            result_obj.output = SimilarOutput(
                errors=[str(exc)],
                warnings=[],
                query_uri=str(URI.from_path(query_path)),
                index_name=index_name,
                embedding_model=spec.embedding_model,
                query_chunk_count=0,
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        embedding_model = spec.embedding_model
        assert embedding_model is not None
        top_limit = top if top is not None else similar_config.top
        per_chunk_limit = per_chunk if per_chunk is not None else similar_config.per_chunk
        candidate_limit = candidates if candidates is not None else similar_config.candidates
        match_cutoff = match_threshold if match_threshold is not None else similar_config.match_threshold
        state = yield from call_with_heartbeat(
            lambda: _SEARCH_RUNTIME.get_semantic_index_state(config, index_name, embedding_model),
            progress=0.55,
            message=f"Loading semantic index '{index_name}'...",
            heartbeat_secs=heartbeat_secs,
        )
        if not state.docs:
            yield (1.0, "Complete")
            error = (
                f"No embeddings found for index '{index_name}' and model '{embedding_model}'. "
                f"Run: wksc index embed {index_name}"
            )
            result_obj.result = error
            result_obj.output = SimilarOutput(
                errors=[error],
                warnings=[],
                query_uri=query_doc.uri,
                index_name=index_name,
                embedding_model=embedding_model,
                query_chunk_count=len(query_doc.chunks),
                candidate_count=0,
                hits=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.66, f"Collecting candidate documents from {len(query_doc.chunks)} query chunks...")
        candidate_scores = _collect_candidate_scores(
            query_doc,
            state,
            per_chunk=per_chunk_limit,
            rrf_k=similar_config.rrf_k,
        )
        ranked_candidate_uris = [
            uri for uri, _ in sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)[:candidate_limit]
        ]
        grouped_rows = _group_candidate_rows(state)

        yield (0.78, f"Reranking {len(ranked_candidate_uris)} candidate documents...")
        hits: list[_CandidateMetrics] = []
        total_candidates = len(ranked_candidate_uris)
        update_every = max(1, total_candidates // 10) if total_candidates > 0 else 1
        for idx, candidate_uri in enumerate(ranked_candidate_uris, start=1):
            if idx == 1 or idx == total_candidates or idx % update_every == 0:
                progress = 0.78 + 0.17 * (idx - 1) / max(total_candidates, 1)
                yield (progress, f"Reranking candidate {idx}/{total_candidates}...")
            row_indices = grouped_rows.get(candidate_uri, [])
            if not row_indices:
                continue
            candidate_docs = [state.docs[idx] for idx in row_indices]
            candidate_matrix = state.matrix[row_indices]
            metrics = _candidate_metrics(
                query_doc=query_doc,
                candidate_uri=candidate_uri,
                candidate_docs=candidate_docs,
                candidate_matrix=candidate_matrix,
                initial_score=candidate_scores[candidate_uri],
                match_threshold=match_cutoff,
                similar_config=similar_config,
            )
            if metrics is not None:
                hits.append(metrics)

        hits.sort(key=lambda item: item.score, reverse=True)
        yield (0.97, "Finalizing ranked hits...")
        output_hits = [
            {
                "uri": hit.uri,
                "label": hit.label,
                "score": hit.score,
                "matched_chunks": hit.matched_chunks,
                "coverage_query": hit.coverage_query,
                "coverage_candidate": hit.coverage_candidate,
                "mean_similarity": hit.mean_similarity,
                "max_similarity": hit.max_similarity,
                "order_consistency": hit.order_consistency,
                "stem_similarity": hit.stem_similarity,
                "path_similarity": hit.path_similarity,
                "evidence": hit.evidence,
            }
            for hit in hits[:top_limit]
        ]

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(output_hits)} similar documents for '{query_doc.uri}'"
        result_obj.output = SimilarOutput(
            errors=[],
            warnings=[],
            query_uri=query_doc.uri,
            index_name=index_name,
            embedding_model=embedding_model,
            query_chunk_count=len(query_doc.chunks),
            candidate_count=len(ranked_candidate_uris),
            hits=output_hits,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Finding similar documents...",
        progress_callback=do_work,
    )
