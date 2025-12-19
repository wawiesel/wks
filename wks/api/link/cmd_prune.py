"""Links prune API command.

CLI: wksc link prune [--domain <domain>]
MCP: wksm_link_prune
"""

import platform
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

from wks.utils.uri_utils import uri_to_path

from ..database.Database import Database
from ..StageResult import StageResult


def cmd_prune(remote: bool = False) -> StageResult:
    """Remove stale links for non-existent monitored files.

    Args:
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        database_name = "link"

        yield (0.3, "Querying database...")
        deleted_count = 0

        with Database(config.database, database_name) as db:
            query: dict[str, object] = {}

            # Find all unique source URIs
            # Note: Database facade doesn't support distinct, so we fetch and aggregate
            docs = list(db.find(query, {"from_uri": 1}))
            unique_uris = {doc["from_uri"] for doc in docs if "from_uri" in doc}

            yield (0.5, f"Checking {len(unique_uris)} source files...")

            uris_to_remove = []
            for uri in unique_uris:
                try:
                    path = uri_to_path(uri)
                    if not path.exists():
                        uris_to_remove.append(uri)
                except Exception:
                    # If URI is invalid or not a file URI, we might want to keep it or handle differently.
                    # For now, ignore non-file URIs or malformed ones unless we are sure.
                    pass

            if uris_to_remove:
                yield (0.8, f"Removing links from {len(uris_to_remove)} stale files...")
                # Delete all links originating from these URIs
                # Construct query: from_uri IN [...] AND source_domain == domain (if specified)
                delete_query: dict[str, Any] = {"from_uri": {"$in": uris_to_remove}}

                deleted_count += db.delete_many(delete_query)

            # Target validation
            yield (0.8, "Checking target validity...")

            # Find all unique target URIs
            docs = list(db.find({}, {"to_uri": 1}))
            unique_targets = {doc["to_uri"] for doc in docs if "to_uri" in doc}

            current_host = platform.node().split(".")[0]
            targets_to_remove = []

            for uri in unique_targets:
                try:
                    parsed = urlparse(uri)
                    if parsed.scheme == "file":
                        # Check hostname
                        # URI format: file://host/path
                        if parsed.netloc == current_host:
                            path = uri_to_path(uri)
                            if not path.exists():
                                targets_to_remove.append(uri)
                        else:
                            # Remote machine file
                            if remote:
                                # TODO: Implement remote check
                                pass
                    elif parsed.scheme in ("http", "https") and remote:
                        # TODO: Implement remote check
                        pass
                except Exception:
                    pass

            if targets_to_remove:
                yield (0.9, f"Removing edges to {len(targets_to_remove)} invalid targets...")
                target_delete_query = {"to_uri": {"$in": targets_to_remove}}
                deleted_count += db.delete_many(target_delete_query)

        yield (1.0, "Complete")
        result_obj.output = {
            "deleted_count": deleted_count,
            "stale_files": len(uris_to_remove) + len(targets_to_remove),
        }
        result_obj.result = (
            f"Cleaned {deleted_count} links (Source: {len(uris_to_remove)}, Target: {len(targets_to_remove)})"
        )
        result_obj.success = True

    return StageResult(
        announce="Cleaning links...",
        progress_callback=do_work,
    )
