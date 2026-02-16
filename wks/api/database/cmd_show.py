"""Show database command."""

import json
from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import DatabaseShowOutput
from .Database import Database


def cmd_show(
    database: str,
    query: str | None = None,
    limit: int = 50,
) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.

        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        from ..config.WKSConfig import WKSConfig

        if limit < 1:
            yield (1.0, "Complete")
            result_obj.result = f"Invalid limit: {limit} (must be >= 1)"
            result_obj.output = DatabaseShowOutput(
                errors=[f"Invalid limit: {limit} (must be >= 1)"],
                warnings=[],
                database=database,
                query={},
                limit=limit,
                count=0,
                results=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        yield (0.3, "Checking database exists...")
        warnings: list[str] = []
        try:
            known = Database.list_databases(config.database)
            prefix = config.database.prefix
            short_names = [n[len(prefix) + 1 :] if n.startswith(f"{prefix}.") else n for n in known]
            if database not in short_names:
                yield (1.0, "Complete")
                result_obj.result = f"Database '{database}' does not exist"
                result_obj.output = DatabaseShowOutput(
                    errors=[f"Database '{database}' does not exist. Known databases: {', '.join(short_names)}"],
                    warnings=[],
                    database=database,
                    query={},
                    limit=limit,
                    count=0,
                    results=[],
                ).model_dump(mode="python")
                result_obj.success = False
                return
        except Exception:
            pass  # Non-critical, proceed with query

        yield (0.4, "Parsing query...")
        try:
            parsed_query = json.loads(query) if query else None
        except json.JSONDecodeError as e:
            yield (1.0, "Complete")
            result_obj.result = f"Invalid JSON: {e}"
            result_obj.output = DatabaseShowOutput(
                errors=[str(e)],
                warnings=[],
                database=database,
                query={},
                limit=limit,
                count=0,
                results=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.7, "Querying database...")
        try:
            # Exclude internal meta documents from results
            base_filter = {"_id": {"$ne": "__meta__"}}
            combined_filter = {"$and": [base_filter, parsed_query]} if parsed_query else base_filter
            query_result = Database.query(config.database, database, combined_filter, limit)
            yield (1.0, "Complete")
            result_obj.result = f"Found {query_result['count']} document(s) in {database}"
            result_obj.output = DatabaseShowOutput(
                errors=[],
                warnings=warnings,
                database=database,
                query=parsed_query or {},
                limit=limit,
                count=query_result["count"],
                results=query_result["results"],
            ).model_dump(mode="python")
            result_obj.success = True
        except Exception as e:
            yield (1.0, "Complete")
            result_obj.result = f"Query failed: {e}"
            result_obj.output = DatabaseShowOutput(
                errors=[str(e)],
                warnings=[],
                database=database,
                query=parsed_query or {},
                limit=limit,
                count=0,
                results=[],
            ).model_dump(mode="python")
            result_obj.success = False

    return StageResult(
        announce=f"Querying {database} database...",
        progress_callback=do_work,
    )
