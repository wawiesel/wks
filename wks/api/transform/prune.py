"""Prune handler for transform database."""

from typing import Any

from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.utils.normalize_path import normalize_path
from wks.utils.uri_to_path import uri_to_path


def prune(config: WKSConfig, **_kwargs: Any) -> dict[str, Any]:
    """Prune transform database.

    Args:
        config: WKS Configuration
        **kwargs: Unused arguments for interface compatibility

    Returns:
        Dict with keys: deleted_count, checked_count, warnings
    """
    transform_deleted = 0
    transform_checked = 0
    warnings: list[str] = []

    with Database(config.database, "transform") as transform_db:
        # Get all cache files on disk
        cache_dir = normalize_path(config.transform.cache.base_dir)
        cache_files: set[str] = set()
        if cache_dir.exists():
            for file in cache_dir.iterdir():
                if file.is_file():
                    # Store just the checksum (filename without extension)
                    cache_files.add(file.stem)

        # Get all checksums in database
        docs = list(transform_db.find({}, {"checksum": 1, "cache_uri": 1}))
        db_checksums: set[str] = set()
        stale_db_records = []

        for doc in docs:
            transform_checked += 1
            checksum = doc["checksum"]
            cache_uri = doc["cache_uri"]
            db_checksums.add(checksum)

            # Check if cache file exists
            try:
                cache_path = uri_to_path(cache_uri) if cache_uri else None
                if cache_path is None or not cache_path.exists():
                    stale_db_records.append(doc["_id"])
            except (ValueError, OSError) as e:
                warnings.append(f"Error checking cache file for {checksum}: {e}")
                stale_db_records.append(doc["_id"])

        # Delete stale DB records (no file on disk)
        if stale_db_records:
            transform_deleted += transform_db.delete_many({"_id": {"$in": stale_db_records}})

        # Delete orphaned files (not in database)
        orphaned_files = cache_files - db_checksums
        for checksum in orphaned_files:
            # We don't know exact extension, try glob
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
