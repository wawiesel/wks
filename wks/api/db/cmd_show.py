"""Show database collection command."""

import json

from ..base import StageResult
from .DbCollection import DbCollection


def cmd_show(
    collection: str,
    query_filter: str | None = None,
    limit: int = 50,
) -> StageResult:
    from ...api.config.WKSConfig import WKSConfig

    config = WKSConfig.load()
    try:
        parsed_query = json.loads(query_filter) if query_filter else None
        result = DbCollection.query(config.db, collection, parsed_query, limit)
        return StageResult(
            announce=f"Showing {collection} collection...",
            result=f"Found {result['count']} document(s)",
            output=result,
            success=True,
        )
    except json.JSONDecodeError as e:
        return StageResult(
            announce=f"Showing {collection}...",
            result=f"Invalid JSON: {e}",
            output={"error": str(e)},
            success=False,
        )
    except Exception as e:
        return StageResult(
            announce=f"Showing {collection}...",
            result=f"Show failed: {e}",
            output={"error": str(e)},
            success=False,
        )
