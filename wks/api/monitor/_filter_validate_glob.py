"""Validation for glob pattern entries in monitor filter lists."""

import fnmatch


def _filter_validate_glob(entry: str) -> str | None:
    """Validate a glob string for monitor filters."""
    entry = entry.strip()
    if not entry:
        return "Glob pattern cannot be empty"
    try:
        fnmatch.fnmatch("test", entry)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        return f"Invalid glob syntax: {exc}"
