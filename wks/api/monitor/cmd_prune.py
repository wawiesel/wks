"""Monitor prune API command.

CLI: wksc monitor prune
MCP: wksm_monitor_prune

Removes documents for files that no longer exist on disk.
"""

from collections.abc import Iterator
from typing import Any

from wks.utils.uri_utils import uri_to_path

from ..database.Database import Database
from ..StageResult import StageResult


def cmd_prune() -> StageResult:
    """Remove stale monitor entries for non-existent files.

    Scans all documents in the monitor database and removes any
    that reference files which no longer exist on disk.
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()
        database_name = "monitor"

        yield (0.3, "Querying database...")
        deleted_count = 0
        checked_count = 0

        with Database(config.database, database_name) as db:
            # Find all documents with uri field
            docs = list(db.find({}, {"_id": 1, "uri": 1}))
            total = len(docs)

            yield (0.4, f"Checking {total} entries...")

            ids_to_remove = []
            for i, doc in enumerate(docs):
                uri = doc.get("uri")
                doc_id = doc.get("_id")

                # Skip meta documents (check if _id is string starting with __)
                if doc_id and isinstance(doc_id, str) and doc_id.startswith("__"):
                    continue

                if uri:
                    checked_count += 1
                    try:
                        path = uri_to_path(uri)
                        if not path.exists():
                            ids_to_remove.append(doc_id)
                    except Exception:
                        # If URI is invalid, keep it (might be external)
                        pass

                # Yield progress
                if i % 100 == 0:
                    progress = 0.4 + (0.5 * (i / max(total, 1)))
                    yield (progress, f"Checked {i}/{total} entries...")

            if ids_to_remove:
                yield (0.9, f"Removing {len(ids_to_remove)} stale entries...")
                db.delete_many({"_id": {"$in": ids_to_remove}})
                deleted_count = len(ids_to_remove)

        yield (1.0, "Complete")
        result_obj.output = {
            "checked_count": checked_count,
            "deleted_count": deleted_count,
        }
        result_obj.result = f"Pruned {deleted_count} stale entries (checked {checked_count})"
        result_obj.success = True

    return StageResult(
        announce="Pruning monitor database...",
        progress_callback=do_work,
    )
