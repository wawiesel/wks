"""Clear transform cache utility."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wks.api.config.WKSConfig import WKSConfig


def clear_transform_cache(config: "WKSConfig") -> None:
    """Clear all files in transform cache directory.

    Per Cache-Database Sync Invariant: reset transform must delete cache files.
    """
    from wks.utils.normalize_path import normalize_path

    cache_dir = normalize_path(config.transform.cache.base_dir)
    if cache_dir.exists():
        for file in cache_dir.iterdir():
            if file.is_file() and file.suffix in (".md", ".txt", ".json"):
                file.unlink()
