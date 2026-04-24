from typing import Any


def rrf_merge(ranked_lists: list[list[dict[str, Any]]], k: int, rrf_k: int = 60) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked):
            key = f"{hit['uri']}:{hit['chunk_index']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
            if key not in docs:
                docs[key] = hit

    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        {**docs[key], "score": round(scores[key], 6)}
        for key in sorted_keys[: k * 3]  # over-return for downstream dedup
    ]
