"""Prune handler for edges database (link)."""

from pathlib import Path
from typing import Any

import requests  # type: ignore

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.utils.has_internet import has_internet
from wks.utils.uri_to_path import uri_to_path


def prune(config: WKSConfig, remote: bool = False, **_kwargs: Any) -> dict[str, Any]:
    """Prune edges database.

    Args:
        config: WKS Configuration
        remote: Check remote targets if True
        **kwargs: Unused arguments for interface compatibility

    Returns:
        Dict with keys: deleted_count, checked_count, warnings
    """
    edges_checked = 0
    edges_deleted = 0
    warnings: list[str] = []

    # Check Internet Availability upfront
    internet_available = False
    if remote:
        internet_available = has_internet()

    # Load valid nodes (for integrity check)
    valid_nodes: set[str] = set()
    with Database(config.database, "nodes") as nodes_db:
        # We assume nodes are already pruned or we accept what's there
        # To be safe, we only consider nodes that actually exist on disk?
        # Replicating cmd_prune logic: it populated valid_nodes either from pruning 'nodes'
        # or loading 'nodes'.
        # Since we are decoupled, we'll just trust the database AND filesystem check here?
        # Actually cmd_prune loaded ALL nodes.
        nodes = nodes_db.find({}, {"local_uri": 1})
        for node in nodes:
            if "local_uri" in node:
                valid_nodes.add(node["local_uri"])

    with Database(config.database, "edges") as edges_db:
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

        for doc in docs:
            should_delete = False

            # 1. Source check
            if doc.get("from_local_uri") not in valid_nodes:
                should_delete = True

            # 2. Determine Local Status
            local_target_broken = False
            to_uri = doc.get("to_local_uri")

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
            remote_uri = doc.get("to_remote_uri")
            if remote and not should_delete and local_target_broken and remote_uri and internet_available:
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
            if remote and internet_available and (from_remote := doc.get("from_remote_uri")):
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
            to_unset_from_remote = [uid for uid in to_unset_from_remote if uid not in to_delete]
            if to_unset_from_remote:
                edges_db.update_many({"_id": {"$in": to_unset_from_remote}}, {"$unset": {"from_remote_uri": ""}})

    return {
        "deleted_count": edges_deleted,
        "checked_count": edges_checked,
        "warnings": warnings,
    }
