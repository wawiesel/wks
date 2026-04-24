"""Search command for lexical BM25 and semantic embedding search."""

from collections.abc import Iterator

from wks.services.search import SearchRequest, search_documents

from ..config.StageResult import StageResult
from . import SearchOutput


def cmd(
    query: str = "",
    index: str = "",
    k: int = 10,
    query_image: str = "",
    strategy: str = "",
) -> StageResult:
    """Search a named index using its configured search mode."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.2, "Preparing search request...")
        response = search_documents(
            SearchRequest(query=query, index=index, k=k, query_image=query_image, strategy=strategy)
        )
        yield (0.8, "Collecting search results...")
        yield (1.0, "Complete")
        result_obj.result = response.message
        result_obj.output = SearchOutput(
            errors=response.errors,
            warnings=response.warnings,
            query=response.query,
            index_name=response.index_name,
            search_mode=response.search_mode,
            embedding_model=response.embedding_model,
            hits=[hit.model_dump(mode="python") for hit in response.hits],
            total_chunks=response.total_chunks,
        ).model_dump(mode="python")
        result_obj.success = response.success

    return StageResult(
        announce=f"Searching for '{query if query.strip() else query_image}'...",
        progress_callback=do_work,
    )
