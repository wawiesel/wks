from pathlib import Path


def _evaluate_roots(path: Path, include_root_set: set[Path], exclude_root_set: set[Path]) -> tuple[bool, str]:
    cur = path
    while True:
        if cur in exclude_root_set:
            return False, f"Excluded by root {cur}"
        if cur in include_root_set:
            return True, f"Included by root {cur}"
        parent = cur.parent
        if parent == cur:
            if include_root_set:
                return False, "Outside include_paths"
            return False, "No include_paths defined; default exclude"
        cur = parent
