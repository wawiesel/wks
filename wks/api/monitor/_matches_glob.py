"""Glob pattern matching helper."""

import fnmatch
from pathlib import Path


def _matches_glob(patterns: list[str], path_obj: Path) -> bool:
    if not patterns:
        return False
    path_str = path_obj.as_posix()
    name = path_obj.name
    for pattern in patterns:
        if not pattern:
            continue
        try:
            if fnmatch.fnmatchcase(path_str, pattern) or fnmatch.fnmatchcase(name, pattern):
                return True
        except Exception:
            continue
    return False
