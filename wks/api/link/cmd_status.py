"""Links status API command.

CLI: wksc links status
MCP: wksm_links_status
"""

from collections.abc import Iterator
from typing import Any

from ..config.StageResult import StageResult
from ..database.Database import Database


def cmd_status() -> StageResult:
    """Get health and statistics for the links collection."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()

        yield (0.3, "Connecting to database...")
        with Database(config.database, "edges") as database:
            total_links = database.count_documents({})

            yield (0.5, "Calculating statistics...")
            # Fetch all edges to count unique nodes
            docs = list(database.find({}, {"from_local_uri": 1, "to_local_uri": 1, "_id": 0}))
            nodes = set()
            for doc in docs:
                if "from_local_uri" in doc:
                    nodes.add(doc["from_local_uri"])
                if "to_local_uri" in doc:
                    nodes.add(doc["to_local_uri"])

            result = {
                "total_links": total_links,
                "total_files": len(nodes),
            }

            yield (1.0, "Complete")
            result_obj.output = result
            result_obj.result = f"Links status: {len(nodes)} files, {total_links} links"
            result_obj.success = True

    return StageResult(
        announce="Fetching links status...",
        progress_callback=do_work,
    )
