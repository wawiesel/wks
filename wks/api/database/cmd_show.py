"""Show database command."""

import json
from collections.abc import Callable

from ..base import StageResult
from .Database import Database


def cmd_show(
    collection: str,
    query_filter: str | None = None,
    limit: int = 50,
) -> StageResult:
    def do_work(update_progress: Callable[[str, float], None], result_obj: StageResult) -> None:
        """Do the actual work - called by wrapper after announce is displayed."""
        from ..config.WKSConfig import WKSConfig

        update_progress("Loading configuration...", 0.2)
        config = WKSConfig.load()
        
        update_progress("Parsing query...", 0.4)
        try:
            parsed_query = json.loads(query_filter) if query_filter else None
        except json.JSONDecodeError as e:
            update_progress("Complete", 1.0)
            result_obj.result = f"Invalid JSON: {e}"
            result_obj.output = {"error": str(e)}
            result_obj.success = False
            return

        update_progress("Querying database...", 0.7)
        try:
            query_result = Database.query(config.database, collection, parsed_query, limit)
            update_progress("Complete", 1.0)
            result_obj.result = f"Found {query_result['count']} document(s) in {collection}"
            result_obj.output = {
                "database": collection,
                "query": parsed_query,
                "limit": limit,
                "count": query_result["count"],
                "results": query_result["results"],
            }
            result_obj.success = True
        except Exception as e:
            update_progress("Complete", 1.0)
            result_obj.result = f"Query failed: {e}"
            result_obj.output = {"error": str(e)}
            result_obj.success = False

    return StageResult(
        announce=f"Querying {collection} database...",
        progress_callback=do_work,
        progress_total=1,
    )
