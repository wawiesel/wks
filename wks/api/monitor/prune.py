"""Prune handler for nodes database (monitor)."""

from typing import Any

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.utils.uri_to_path import uri_to_path


def prune(config: WKSConfig, **_kwargs: Any) -> dict[str, Any]:
    """Prune nodes database.

    Args:
        config: WKS Configuration
        **kwargs: Unused arguments for interface compatibility

    Returns:
        Dict with keys: deleted_count, checked_count, warnings
    """
    nodes_checked = 0
    nodes_deleted = 0
    warnings: list[str] = []

    with Database(config.database, "nodes") as nodes_db:
        # Find all documents with URI
        start_docs = list(nodes_db.find({}, {"local_uri": 1}))
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
                except OSError as e:
                    # Filesystem error - track as warning, keep document
                    warnings.append(f"Filesystem error for {uri}: {e}")

        if ids_to_remove:
            nodes_deleted = nodes_db.delete_many({"_id": {"$in": ids_to_remove}})

    return {
        "deleted_count": nodes_deleted,
        "checked_count": nodes_checked,
        "warnings": warnings,
    }
