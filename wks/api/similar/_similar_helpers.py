"""Shared helpers for document-similarity scoring and labeling."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from ..config.URI import URI
from ..config.WKSConfig import WKSConfig
from ..index._embedding_utils import cosine_scores
from ..index._IndexSpec import _IndexSpec
from ..search._SearchRuntime import _SemanticIndexState
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
    for row_idx in range(rows):
        for col_idx in range(cols):
            score = float(similarity[row_idx, col_idx])
            if score >= match_threshold:
                pairs.append((score, row_idx, col_idx))
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
