"""Find the deepest matching priority directory for a path."""

from pathlib import Path


def _priority_find_priority_dir(path: Path, priority_dirs: dict[str, float]) -> tuple[Path | None, float]:
    path = path.resolve()
    resolved_priority = {Path(k).expanduser().resolve(): v for k, v in priority_dirs.items()}

    ancestors = [path, *list(path.parents)]
    best_match = None
    best_priority = 100.0

    for ancestor in ancestors:
        if ancestor in resolved_priority and (best_match is None or len(ancestor.parts) > len(best_match.parts)):
            best_match = ancestor
            best_priority = float(resolved_priority[ancestor])

    return best_match, best_priority

