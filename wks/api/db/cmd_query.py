"""Query database command."""

import json
from typing import Any

import typer

from ..base import StageResult
from .DbCollection import DbCollection


def cmd_query(
    collection: str = typer.Argument(..., help="Collection name (e.g., 'monitor')"),
    query_filter: str | None = typer.Option(None, "--query", "-q", help="Query filter as JSON string (MongoDB-style, e.g., '{\"status\": \"active\"}' or '{\"age\": {\"$gt\": 18}}')"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of documents to return"),
) -> StageResult:
    parsed_query = json.loads(query_filter) if query_filter else None

    try:
        result = DbCollection.query(collection, parsed_query, limit)
        return StageResult(
            announce=f"Querying {collection} collection...",
            result=f"Found {result['count']} document(s)",
            output=result,
            success=True,
        )
    except json.JSONDecodeError as e:
        return StageResult(announce=f"Querying {collection}...", result=f"Invalid JSON: {e}", output={"error": str(e)}, success=False)
    except Exception as e:
        return StageResult(announce=f"Querying {collection}...", result=f"Query failed: {e}", output={"error": str(e)}, success=False)
