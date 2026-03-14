"""Backfill an index from the monitor database.

Indexes all monitored files that meet the index's min_priority threshold
but have not yet been added to the chunk store. Safe to re-run — skips
files whose checksum hasn't changed since last index.
"""

from collections.abc import Iterator

from ..config.StageResult import StageResult


def cmd_backfill(name: str = "") -> StageResult:
    """Index all monitored files that meet the index's min_priority threshold."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.05, "Loading configuration...")
        from ..config.WKSConfig import WKSConfig

        config = WKSConfig.load()

        if config.index is None:
            result_obj.result = "No index configuration"
            result_obj.success = False
            result_obj.output = {"errors": ["No index section in config"], "indexed": 0, "skipped": 0}
            yield (1.0, "Complete")
            return

        index_name = name if name else config.index.default_index
        if index_name not in config.index.indexes:
            result_obj.result = f"Unknown index: {index_name}"
            result_obj.success = False
            result_obj.output = {
                "errors": [f"Index '{index_name}' not defined in config"],
                "indexed": 0,
                "skipped": 0,
            }
            yield (1.0, "Complete")
            return

        spec = config.index.indexes[index_name]
        min_priority = spec.min_priority

        yield (0.1, f"Querying monitor DB for files with priority >= {min_priority}...")
        from ..database.Database import Database

        with Database(config.database, "nodes") as nodes_db:
            candidates = list(nodes_db.find({"priority": {"$gte": min_priority}}, {"local_uri": 1}))

        uris = [doc["local_uri"] for doc in candidates if "local_uri" in doc]
        total = len(uris)
        yield (0.15, f"Found {total} candidate files in monitor DB...")

        if total == 0:
            result_obj.result = "No monitored files meet min_priority threshold"
            result_obj.success = True
            result_obj.output = {"errors": [], "indexed": 0, "skipped": 0}
            yield (1.0, "Complete")
            return

        from ..index.cmd_auto import cmd_auto

        indexed = 0
        skipped = 0
        errors: list[str] = []

        for i, uri in enumerate(uris):
            progress = 0.15 + (i / total) * 0.8
            try:
                res = cmd_auto(uri)
                list(res.progress_callback(res))
                if res.success:
                    out = res.output
                    if out.get("indexed"):
                        indexed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors.append(f"{uri}: {exc}")
                skipped += 1

            if i % 50 == 0 or i == total - 1:
                yield (progress, f"Processed {i + 1}/{total} — indexed {indexed}, skipped {skipped}...")

        result_obj.result = f"Backfill '{index_name}': {indexed} indexed, {skipped} skipped"
        result_obj.success = True
        result_obj.output = {"errors": errors, "indexed": indexed, "skipped": skipped}
        yield (1.0, "Complete")

    return StageResult(
        announce=f"Backfilling index '{name or '(default)'}'...",
        progress_callback=do_work,
    )
