from pathlib import Path

from ._auto_index import _auto_index


def _sync_path_static(path: Path, _log_file: Path, log_fn) -> None:
    """Invoke monitor sync for a single path (child process safe)."""
    try:
        from ..config.URI import URI
        from ..monitor.cmd_sync import cmd_sync

        result = cmd_sync(URI.from_path(path))
        list(result.progress_callback(result))
        out = result.output
        for msg in out["warnings"]:
            log_fn(f"WARN: {msg}")
        for msg in out["errors"]:
            log_fn(f"ERROR: {msg}")

        # Auto-index if file was synced (not deleted or skipped)
        if result.success and out["files_synced"] > 0:
            _auto_index(path, log_fn)
    except RuntimeError as exc:
        if "mongod binary not found" in str(exc):
            log_fn(f"ERROR: Database binary missing during sync: {exc}")
        else:
            log_fn(f"ERROR: sync failed for {path}: {exc}")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_fn(f"ERROR: sync failed for {path}: {exc}")
