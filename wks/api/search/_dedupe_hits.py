"""Deduplicate ranked hits by canonical URI and text content hash."""

from hashlib import sha256
from typing import Any

from ..config.URI import URI


def _dedupe_hits(hits: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """Keep score order while removing duplicate document representations."""
    deduped: list[dict[str, Any]] = []
    seen_uris: set[str] = set()
    seen_hashes: set[str] = set()

    for hit in hits:
        canonical_uri = str(URI.from_any(hit["uri"]))
        text_hash = sha256(hit["text"].encode("utf-8")).hexdigest()

        if canonical_uri in seen_uris or text_hash in seen_hashes:
            continue

        deduped.append(
            {
                "uri": canonical_uri,
                "chunk_index": hit["chunk_index"],
                "score": hit["score"],
                "tokens": hit["tokens"],
                "text": hit["text"],
            }
        )
        seen_uris.add(canonical_uri)
        seen_hashes.add(text_hash)

        if len(deduped) >= k:
            break

    return deduped
