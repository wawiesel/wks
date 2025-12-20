"""Database prune API command.

CLI: wksc database prune <database>
MCP: wksm_database_prune
"""

from collections.abc import Iterator
from typing import Any

from wks.utils.uri_utils import uri_to_path

from ..StageResult import StageResult
from . import DatabasePruneOutput
from .Database import Database


def cmd_prune(database: str, remote: bool = False) -> StageResult:
    """Prune stale data from the specified database.

    Args:
        database: "nodes", "edges", or "all".
        remote: Check remote targets if applicable.
    """
    # Silencing unused argument warning until implemented
    _ = remote

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()

        # Decide what to prune
        targets = []
        if database in ("all", "nodes", "monitor"):
            targets.append("nodes")
        if database in ("all", "edges", "link"):
            targets.append("edges")

        # If 'all' or specific target not recognized (though CLI should handle verification),
        # but here we allow flexibility. If nothing matched (e.g. unknown), we do nothing.

        total_deleted = 0
        total_checked = 0

        # We need to maintain state across prune operations if 'all' is used
        # But StageResult only returns one output object.
        # The spec says `DatabasePruneOutput` returns specific fields.
        # If 'all' is run, we might need to aggregate or return a list?
        # The spec defines `DatabasePruneOutput` with `database`, `deleted_count`, `checked_count`.
        # If 'all' is run, the CLI/MCP might expect a single result.
        # However, for 'all', we usually want aggregate stats.
        # Let's conform to returning the aggregate stats in `DatabasePruneOutput`
        # but set 'database' to the input argument (e.g. "all").

        # 1. Prune Nodes (Monitor)
        valid_nodes: set[str] = set()

        if "nodes" in targets:
            yield (0.2, "Pruning nodes database...")
            with Database(config.database, "nodes") as nodes_db:
                # Find all documents with URI
                start_docs = list(nodes_db.find({}, {"local_uri": 1}))
                nodes_checked = 0
                nodes_deleted = 0
                ids_to_remove = []

                for doc in start_docs:
                    if "local_uri" in doc:
                        nodes_checked += 1
                        uri = doc["local_uri"]
                        # Check filesystem
                        try:
                            path = uri_to_path(uri)
                            if not path.exists():
                                ids_to_remove.append(doc["_id"])
                            else:
                                valid_nodes.add(uri)
                        except Exception:
                            # Keep if can't parse? Or remove?
                            # Strict: if invalid URI, maybe remove.
                            pass

                if ids_to_remove:
                    nodes_deleted = nodes_db.delete_many({"_id": {"$in": ids_to_remove}})

                total_checked += nodes_checked
                total_deleted += nodes_deleted

                # If we pruned nodes, we must re-populate valid_nodes for edges check
                # actually, `valid_nodes` checks above already exclude deleted ones.

        # If we didn't run nodes prune but we need to run edges prune, we MUST load valid nodes first
        if "edges" in targets and "nodes" not in targets:
            yield (0.4, "Loading monitor index for integrity check...")
            with Database(config.database, "nodes") as nodes_db:
                nodes = nodes_db.find({}, {"local_uri": 1})
                for node in nodes:
                    if "local_uri" in node:
                        valid_nodes.add(node["local_uri"])

        # 2. Prune Edges (Link)
        if "edges" in targets:
            yield (0.6, "Pruning edges database...")
            edges_checked = 0
            edges_deleted = 0

            with Database(config.database, "edges") as edges_db:
                # Check Sources
                docs = list(edges_db.find({}, {"from_local_uri": 1, "to_local_uri": 1}))
                edges_checked = len(docs)

                to_delete = []

                # We can do this in memory or query. Memory is safer for complex logic.
                for doc in docs:
                    should_delete = False

                    # 1. Source check
                    if doc.get("from_local_uri") not in valid_nodes:
                        should_delete = True

                    # 2. Target check - REMOVED
                    # We cannot safely prune based on target validity because:
                    # a) The target might be a valid file that is simply not monitored (not in nodes).
                    # b) Remote edges logic is complex.
                    # Per feedback, we must preserve edges even if target is not in valid_nodes to avoid data loss.
                    # We only prune "orphaned" edges where the SOURCE is gone.

                    # TODO: Remote check

                    if should_delete:
                        to_delete.append(doc["_id"])

                if to_delete:
                    edges_deleted = edges_db.delete_many({"_id": {"$in": to_delete}})

                total_checked += edges_checked
                total_deleted += edges_deleted

        yield (1.0, "Complete")

        result_obj.output = DatabasePruneOutput(
            errors=[], warnings=[], database=database, deleted_count=total_deleted, checked_count=total_checked
        ).model_dump(mode="python")

        result_obj.result = f"Pruned {database}: Checked {total_checked}, Deleted {total_deleted}"
        result_obj.success = True

    return StageResult(
        announce=f"Pruning {database}...",
        progress_callback=do_work,
    )
