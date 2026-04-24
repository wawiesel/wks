from pathlib import Path

from wks.api.config.get_wks_home import get_wks_home
from wks.api.config.normalize_path import normalize_path

from ._evaluate_roots import _evaluate_roots
from .matches_glob import matches_glob
from .MonitorConfig import MonitorConfig


def explain_path(cfg: MonitorConfig, path: Path) -> tuple[bool, list[str]]:
    trace: list[str] = []
    resolved = normalize_path(path)

    wks_home = get_wks_home()
    try:
        if resolved == wks_home or resolved.is_relative_to(wks_home):
            trace.append(f"In WKS home directory {wks_home} (automatically ignored)")
            return False, trace
    except ValueError:
        pass

    include_roots = [normalize_path(p) for p in cfg.filter.include_paths]
    exclude_roots = [normalize_path(p) for p in cfg.filter.exclude_paths]
    include_root_set = set(include_roots)
    exclude_root_set = set(exclude_roots)
    include_dirnames = {d.strip() for d in cfg.filter.include_dirnames if d and d.strip()}
    exclude_dirnames = {d.strip() for d in cfg.filter.exclude_dirnames if d and d.strip()}
    include_globs = [g.strip() for g in cfg.filter.include_globs if g]
    exclude_globs = [g.strip() for g in cfg.filter.exclude_globs if g]

    root_allowed, root_reason = _evaluate_roots(resolved, include_root_set, exclude_root_set)
    trace.append(root_reason)
    if not root_allowed:
        return False, trace

    excluded = False

    for p in resolved.parents:
        if p.name in exclude_dirnames:
            trace.append(f"Parent dir '{p.name}' excluded")
            excluded = True
            break

    if not excluded and resolved.name in exclude_dirnames:
        trace.append(f"Directory '{resolved.name}' excluded")
        excluded = True

    if not excluded and matches_glob(exclude_globs, resolved):
        trace.append("Excluded by glob pattern")
        excluded = True

    if excluded:
        parent = resolved.parent.name if resolved.parent != resolved else ""
        if parent in include_dirnames:
            trace.append(f"Parent dir '{parent}' override")
            return True, trace

        if matches_glob(include_globs, resolved):
            trace.append("Included by glob override")
            return True, trace
        return False, trace

    return True, trace
