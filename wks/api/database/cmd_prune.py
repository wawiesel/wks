"""Database prune API command.

CLI: wksc database prune <database>
MCP: wksm_database_prune
"""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests

from ...utils.uri_to_path import uri_to_path
from ..StageResult import StageResult
from . import DatabasePruneOutput
from .Database import Database


def _has_internet(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Check for internet connectivity."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except OSError:
        return False


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
        all_warnings: list[str] = []

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
                        except ValueError as e:
                            # Invalid URI format - track as warning, keep document
                            all_warnings.append(f"Invalid URI format in nodes: {uri} ({e})")

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
            # Check Internet Availability upfront
            internet_available = False
            if remote:
                internet_available = _has_internet()

            with Database(config.database, "edges") as edges_db:
                # Check Sources
                docs = list(
                    edges_db.find(
                        {},
                        {
                            "from_local_uri": 1,
                            "to_local_uri": 1,
                            "to_remote_uri": 1,
                            "from_remote_uri": 1,
                        },
                    )
                )
                edges_checked = len(docs)

                to_delete = []
                to_unset_to_remote = []
                to_unset_from_remote = []

                # We can do this in memory or query. Memory is safer for complex logic.
                for doc in docs:
                    should_delete = False

                    # 1. Source check
                    if doc["from_local_uri"] not in valid_nodes:
                        should_delete = True

                    # 2. Determine Local Status
                    local_target_broken = False
                    to_uri = doc["to_local_uri"]

                    if not to_uri:
                        # Empty local target
                        local_target_broken = True  # Treated as "broken" for purpose of fallback check
                    elif to_uri not in valid_nodes:
                        # Not monitored. Check filesystem.
                        try:
                            path_str = uri_to_path(to_uri)
                            if not Path(path_str).exists():
                                local_target_broken = True
                        except ValueError:
                            local_target_broken = True

                    # 3. Remote Check
                    remote_uri = doc["to_remote_uri"]
                    if remote and not should_delete and local_target_broken and remote_uri:
                        if not internet_available:
                            # Skip check if offline
                            pass
                        else:
                            try:
                                # Use HEAD to be efficient
                                response = requests.head(remote_uri, timeout=5)
                                if response.status_code in (404, 410):
                                    to_unset_to_remote.append(doc["_id"])
                                    remote_uri = None

                            except (requests.RequestException, ValueError):
                                # Transient error or invalid URL -> Persist safely
                                pass

                    # 4. From Remote Check
                    # Check from_remote_uri independently.
                    if remote and internet_available and (from_remote := doc["from_remote_uri"]):
                        try:
                            response = requests.head(from_remote, timeout=5)
                            if response.status_code in (404, 410):
                                to_unset_from_remote.append(doc["_id"])
                        except (requests.RequestException, ValueError):
                            pass

                    # 5. Final Decision
                    if not should_delete and local_target_broken and not remote_uri:
                        should_delete = True

                    if should_delete:
                        to_delete.append(doc["_id"])

                if to_delete:
                    # Filter out IDs that are being deleted from unset lists to avoid redundant update
                    to_unset_to_remote = [uid for uid in to_unset_to_remote if uid not in to_delete]
                    to_unset_from_remote = [uid for uid in to_unset_from_remote if uid not in to_delete]
                    edges_deleted = edges_db.delete_many({"_id": {"$in": to_delete}})

                if to_unset_to_remote:
                    edges_db.update_many({"_id": {"$in": to_unset_to_remote}}, {"$unset": {"to_remote_uri": ""}})

                if to_unset_from_remote:
                    # Filter: skip already-deleted edges
                    to_unset_from_remote = [uid for uid in to_unset_from_remote if uid not in to_delete]
                    if to_unset_from_remote:
                        edges_db.update_many(
                            {"_id": {"$in": to_unset_from_remote}}, {"$unset": {"from_remote_uri": ""}}
                        )

                total_checked += edges_checked
                total_deleted += edges_deleted

        yield (1.0, "Complete")

        result_obj.output = DatabasePruneOutput(
            errors=[],
            warnings=all_warnings,
            database=database,
            deleted_count=total_deleted,
            checked_count=total_checked,
        ).model_dump(mode="python")

        result_obj.result = f"Pruned {database}: Checked {total_checked}, Deleted {total_deleted}"
        result_obj.success = True

    return StageResult(
        announce=f"Pruning {database}...",
        progress_callback=do_work,
    )
