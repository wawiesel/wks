"""Auto-index a synced file into matching indexes."""

from collections.abc import Callable
from pathlib import Path


def _auto_index(path: Path, log_fn: Callable[[str], None]) -> None:
    """Index a file into all indexes whose min_priority threshold is met."""
    try:
        from ..config.URI import URI
        from ..index.cmd_auto import cmd_auto

        result = cmd_auto(str(URI.from_path(path)))
        list(result.progress_callback(result))

        if not result.success:
            for err in result.output.get("errors", []):
                log_fn(f"WARN: auto-index: {err}")
            return

        for entry in result.output.get("indexed", []):
            log_fn(f"INFO: auto-indexed {path.name} into '{entry['index_name']}' ({entry['chunk_count']} chunks)")
    except Exception as exc:
        log_fn(f"WARN: auto-index error for {path}: {exc}")
