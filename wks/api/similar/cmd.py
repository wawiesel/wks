"""Prototype document-similarity command built from chunk similarity."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from ..config._progress_heartbeat import call_with_heartbeat, relay_stage_with_heartbeat
from ..config.StageResult import StageResult
from ..config.URI import URI
from ..index._build_semantic_embeddings import build_semantic_embeddings
from ..index._SlidingWindowChunker import _SlidingWindowChunker
from ..search._SearchRuntime import _SEARCH_RUNTIME
from ..transform.cmd_engine import cmd_engine
from ..transform.get_content import get_content
from . import SimilarOutput
from ._similar_helpers import (
    _candidate_metrics,
    _CandidateMetrics,
    _collect_candidate_scores,
    _file_checksum,
    _group_candidate_rows,
    _path_segments,
    _QueryDoc,
    _resolve_semantic_index,
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
