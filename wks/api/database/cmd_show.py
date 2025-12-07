"""Show database command."""

import json

from ..base import StageResult
from .Database import Database


def cmd_show(
    collection: str,
    query_filter: str | None = None,
    limit: int = 50,
) -> StageResult:
    from ..config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    try:
        parsed_query = json.loads(query_filter) if query_filter else None
        query_result = Database.query(config.database, collection, parsed_query, limit)

        return StageResult(
            announce=f"Querying {collection} database...",
            result=f"Found {query_result['count']} document(s) in {collection}",
            output={
                "database": collection,
                "query": parsed_query,
                "limit": limit,
                "count": query_result["count"],
                "results": query_result["results"],
            },
            success=True,
        )
    except json.JSONDecodeError as e:
        return StageResult(
            announce=f"Querying {collection} database...",
            result=f"Invalid JSON: {e}",
            output={"error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce=f"Querying {collection} database...",
            result=f"Query failed: {e}",
            output={"error": str(e)},
            success=False,
        )
