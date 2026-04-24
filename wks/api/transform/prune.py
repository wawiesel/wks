from typing import Any

from wks.api.config.normalize_path import normalize_path
from wks.api.config.URI import URI
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database


def prune(config: WKSConfig, **_kwargs: Any) -> dict[str, Any]:
    transform_deleted = 0
    transform_checked = 0
    warnings: list[str] = []

    with Database(config.database, "transform") as transform_db:
        cache_dir = normalize_path(config.transform.cache.base_dir)
        cache_files: set[str] = set()
        if cache_dir.exists():
            for file in cache_dir.iterdir():
                if file.is_file():
                    cache_files.add(file.stem)

        docs = list(transform_db.find({}, {"checksum": 1, "cache_uri": 1}))
        db_checksums: set[str] = set()
        stale_db_records = []

        for doc in docs:
            transform_checked += 1
            checksum = doc["checksum"]
            cache_uri = doc["cache_uri"]
            db_checksums.add(checksum)

            try:
                cache_path = URI(cache_uri).path if cache_uri else None
                if cache_path is None or not cache_path.exists():
                    stale_db_records.append(doc["_id"])
            except (ValueError, OSError) as e:
                warnings.append(f"Error checking cache file for {checksum}: {e}")
                stale_db_records.append(doc["_id"])

        if stale_db_records:
            transform_deleted += transform_db.delete_many({"_id": {"$in": stale_db_records}})

        orphaned_files = cache_files - db_checksums
        for checksum in orphaned_files:
            for file in cache_dir.glob(f"{checksum}.*"):
                try:
                    file.unlink()
                    transform_deleted += 1
                except OSError as e:
                    warnings.append(f"Failed to delete orphaned file {file}: {e}")

    return {
        "deleted_count": transform_deleted,
        "checked_count": transform_checked,
        "warnings": warnings,
    }
