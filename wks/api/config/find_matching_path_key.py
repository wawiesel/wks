"""Find the key in a path map that canonically matches candidate.

This function is useful for finding dictionary keys that represent paths,
even if the key and candidate use different path representations (e.g., ~ vs absolute).
"""

from .normalize_path import normalize_path


def find_matching_path_key(path_map: dict, candidate: str) -> str | None:
    """Find the key in a path map that canonically matches candidate.

    This function is useful for finding dictionary keys that represent paths,
    even if the key and candidate use different path representations (e.g., ~ vs absolute).

    Args:
        path_map: Dictionary with path strings as keys
        candidate: Path string to find a matching key for

    Returns:
        Matching key from path_map if found, None otherwise

    Examples:
        >>> path_map = {"~/Documents": 100, "/tmp": 50}
        >>> find_matching_path_key(path_map, "~/Documents")
        "~/Documents"
        >>> find_matching_path_key(path_map, "/Users/user/Documents")
        "~/Documents"
        >>> find_matching_path_key(path_map, "/nonexistent")
        None
    """
    candidate_norm = str(normalize_path(candidate))
    for key in path_map:
        if str(normalize_path(key)) == candidate_norm:
            return key
    return None
