from pathlib import Path

from wks.api.config.normalize_path import normalize_path


def find_priority_dir(path: Path, priority_dirs: dict[str, float]) -> tuple[Path | None, float]:
    path = normalize_path(path)
    resolved_priority = {normalize_path(k): v for k, v in priority_dirs.items()}

    ancestors = [path, *list(path.parents)]
    best_match = None
    best_priority = 100.0

    for ancestor in ancestors:
        if ancestor in resolved_priority and (best_match is None or len(ancestor.parts) > len(best_match.parts)):
            best_match = ancestor
            best_priority = float(resolved_priority[ancestor])

    return best_match, best_priority
