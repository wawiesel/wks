"""Similar API module."""

from wks.api.config.output_models import output_model

SimilarOutput = output_model(
    "SimilarOutput", "query_uri", "index_name", "embedding_model", "query_chunk_count", "candidate_count", "hits"
)

__all__ = ["SimilarOutput"]
