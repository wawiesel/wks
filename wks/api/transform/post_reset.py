"""Hook called after database reset for transform domain."""

from typing import Any


def post_reset(config: Any) -> None:
    """Clear all files in transform cache directory.

    Per Cache-Database Sync Invariant: reset transform must delete cache files.
    """
    from wks.utils.normalize_path import normalize_path

    cache_dir = normalize_path(config.transform.cache.base_dir)
    if cache_dir.exists():
        for file in cache_dir.iterdir():
            if file.is_file() and file.suffix in (".md", ".txt", ".json"):
                file.unlink()
