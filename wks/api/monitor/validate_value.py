"""Validate filter value helper."""

import fnmatch
from pathlib import Path
from typing import Any

from wks.api.config.canonicalize_path import canonicalize_path


def validate_value(list_name: str, value: str, monitor_cfg: Any) -> tuple[str | None, str | None]:
    """Validate and normalize a value for a filter list."""
    value = value.strip()
    if list_name in ("include_paths", "exclude_paths"):
        value_resolved = canonicalize_path(value)
        home_dir = str(Path.home())
        if value_resolved.startswith(home_dir):
            return "~" + value_resolved[len(home_dir) :], None
        return value_resolved, None

    if list_name in ("include_dirnames", "exclude_dirnames"):
        if not value:
            return None, "Directory name cannot be empty"
        if any(ch in value for ch in "*?[]"):
            return None, "Directory names cannot contain wildcard characters"
        if "/" in value or "\\" in value:
            return None, "Directory names cannot contain path separators"

        opposite = "exclude_dirnames" if list_name == "include_dirnames" else "include_dirnames"
        if value in getattr(monitor_cfg.filter, opposite):
            return None, f"Directory name '{value}' already present in {opposite}"
        return value, None

    if list_name in ("include_globs", "exclude_globs"):
        if not value:
            return None, "Glob pattern cannot be empty"
        try:
            fnmatch.fnmatch("test", value)
            return value, None
        except Exception as exc:
            return None, f"Invalid glob syntax: {exc}"

    return value, None
