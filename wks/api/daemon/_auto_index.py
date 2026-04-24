from collections.abc import Callable
from pathlib import Path


def _auto_index(path: Path, log_fn: Callable[[str], None]) -> None:
    try:
        from ..config.URI import URI
        from ..index.cmd_auto import cmd_auto

        uri = str(URI.from_path(path))
        result = cmd_auto(uri)
        list(result.progress_callback(result))

        if not result.success:
            for err in result.output["errors"]:
                log_fn(f"WARN: auto-index: {err}")
            return

        for entry in result.output["indexed"]:
            log_fn(f"INFO: auto-indexed {path.name} into '{entry['index_name']}' ({entry['chunk_count']} chunks)")

    except Exception as exc:
        log_fn(f"WARN: auto-index error for {path}: {exc}")
