from typing import Any


def post_reset(config: Any) -> None:
    from wks.api.config.normalize_path import normalize_path

    cache_dir = normalize_path(config.transform.cache.base_dir)
    if cache_dir.exists():
        for file in cache_dir.iterdir():
            if file.is_file() and file.suffix in (".md", ".txt", ".json"):
                file.unlink()
