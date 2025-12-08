"""Show database command."""

import json
from collections.abc import Iterator

from ..StageResult import StageResult
from .Database import Database


def cmd_show(
    collection: str,
    query_filter: str | None = None,
    limit: int = 50,
) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.4, "Parsing query...")
        try:
            parsed_query = json.loads(query_filter) if query_filter else None
        except json.JSONDecodeError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Invalid JSON: {e}"
            result_obj.output = {
                "errors": [str(e)],
                "warnings": [],
                "database": collection,
                "query": {},
                "limit": limit,
                "count": 0,
                "results": [],
            }
            result_obj.success = False
            return

        yield (0.7, "Querying database...")
        try:
            query_result = Database.query(config.database, collection, parsed_query, limit)
            yield (1.0, "Complete")
            result_obj.result = f"Found {query_result['count']} document(s) in {collection}"
            result_obj.output = {
                "errors": [],
                "warnings": [],
                "database": collection,
                "query": parsed_query or {},
                "limit": limit,
                "count": query_result["count"],
                "results": query_result["results"],
            }
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Query failed: {e}"
            result_obj.output = {
                "errors": [str(e)],
                "warnings": [],
                "database": collection,
                "query": parsed_query or {},
                "limit": limit,
                "count": 0,
                "results": [],
            }
            result_obj.success = False

    return StageResult(
        announce=f"Querying {collection} database...",
        progress_callback=do_work,
    )
