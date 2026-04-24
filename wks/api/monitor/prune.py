from typing import Any

from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database


def prune(config: WKSConfig, **_kwargs: Any) -> dict[str, Any]:
    import socket

    nodes_checked = 0
    nodes_deleted = 0
    warnings: list[str] = []
    current_hostname = socket.gethostname()

    with Database(config.database, "nodes") as nodes_db:
        start_docs = list(nodes_db.find({}, {"local_uri": 1}))
        ids_to_remove = []

        for doc in start_docs:
            if "local_uri" in doc:
                nodes_checked += 1
                uri = doc["local_uri"]

                if uri.startswith("file://"):
                    uri_hostname = uri[7:].split("/", 1)[0]
                    if uri_hostname and uri_hostname != current_hostname:
                        ids_to_remove.append(doc["_id"])
                        continue

                try:
                    if not URI(uri).path.exists():
                        ids_to_remove.append(doc["_id"])
                except OSError as e:
                    warnings.append(f"Filesystem error for {uri}: {e}")

        if ids_to_remove:
            nodes_deleted = nodes_db.delete_many({"_id": {"$in": ids_to_remove}})

    return {
        "deleted_count": nodes_deleted,
        "checked_count": nodes_checked,
        "warnings": warnings,
    }
