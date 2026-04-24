from .normalize_path import normalize_path


def find_matching_path_key(path_map: dict, candidate: str) -> str | None:
    candidate_norm = str(normalize_path(candidate))
    for key in path_map:
        if str(normalize_path(key)) == candidate_norm:
            return key
    return None
