"""Search API module."""

from wks.api.config.output_models import output_model

SearchOutput = output_model(
    "SearchOutput", "query", "index_name", "search_mode", "embedding_model", "hits", "total_chunks"
)

__all__ = ["SearchOutput"]
