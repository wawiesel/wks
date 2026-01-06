from pathlib import Path


def _sync_path_static(path: Path, _log_file: Path, log_fn) -> None:
    """Invoke monitor sync for a single path (child process safe)."""
    try:
        from ..config.URI import URI
        from ..monitor.cmd_sync import cmd_sync

        result = cmd_sync(URI.from_path(path))
        list(result.progress_callback(result))
        out = result.output or {}
        errs = out["errors"]
        warns = out["warnings"]
        for msg in warns:
            log_fn(f"WARN: {msg}")
        for msg in errs:
            log_fn(f"ERROR: {msg}")
    except RuntimeError as exc:
        # If it's the "mongod binary not found" error, log it as FATAL once and re-raise/stop?
        # Actually, if we are in _sync_path_static, we are inside the loop.
        # But we added a pre-flight check, so this should not happen often.
        if "mongod binary not found" in str(exc):
            log_fn(f"ERROR: Database binary missing during sync: {exc}")
        else:
            log_fn(f"ERROR: sync failed for {path}: {exc}")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_fn(f"ERROR: sync failed for {path}: {exc}")
