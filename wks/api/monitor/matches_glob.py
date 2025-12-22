"""Glob pattern matching helper."""

import fnmatch
from pathlib import Path


def matches_glob(patterns: list[str], path_obj: Path) -> bool:
    """Check if path matches any of the glob patterns.

    Args:
        patterns: List of glob patterns to match against
        path_obj: Path to check

    Returns:
        True if path matches any pattern, False otherwise
    """
    if not patterns:
        return False
    path_str = path_obj.as_posix()
    name = path_obj.name
    for pattern in patterns:
        if not pattern:
            continue
        # fnmatch.fnmatchcase does not raise exceptions for valid patterns
        # Invalid patterns are programming errors and should propagate
        if fnmatch.fnmatchcase(path_str, pattern) or fnmatch.fnmatchcase(name, pattern):
            return True
    return False
