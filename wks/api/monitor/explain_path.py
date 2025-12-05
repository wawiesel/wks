"""Explain why a path is allowed or excluded by monitor rules."""

from pathlib import Path

from ..config.get_home_dir import get_home_dir
from ._evaluate_roots import _evaluate_roots
from ._matches_glob import _matches_glob
from .MonitorConfig import MonitorConfig


def explain_path(cfg: MonitorConfig, path: Path) -> tuple[bool, list[str]]:
    """Explain why a path is allowed or excluded."""
    trace: list[str] = []
    resolved = path.expanduser().resolve()

    # Check if path is within WKS home directory (automatically excluded)
    wks_home = get_home_dir()
    try:
        if resolved == wks_home or resolved.is_relative_to(wks_home):
            trace.append(f"In WKS home directory {wks_home} (automatically ignored)")
            return False, trace
    except ValueError:
        # Paths on different drives (Windows) - check string prefix instead
        if str(resolved).startswith(str(wks_home) + "/") or str(resolved).startswith(str(wks_home) + "\\"):
            trace.append(f"In WKS home directory {wks_home} (automatically ignored)")
            return False, trace

    # Normalize filter lists
    include_roots = [Path(p).expanduser().resolve() for p in cfg.filter.include_paths]
    exclude_roots = [Path(p).expanduser().resolve() for p in cfg.filter.exclude_paths]
    include_root_set = set(include_roots)
    exclude_root_set = set(exclude_roots)
    include_dirnames = {d.strip() for d in cfg.filter.include_dirnames if d and d.strip()}
    exclude_dirnames = {d.strip() for d in cfg.filter.exclude_dirnames if d and d.strip()}
    include_globs = [g.strip() for g in cfg.filter.include_globs if g]
    exclude_globs = [g.strip() for g in cfg.filter.exclude_globs if g]

    # Evaluate root paths
    root_allowed, root_reason = _evaluate_roots(resolved, include_root_set, exclude_root_set)
    trace.append(root_reason)
    if not root_allowed:
        return False, trace

    # Check dirname and glob exclusions
    parent = resolved.parent.name if resolved.parent != resolved else ""
    excluded = False
    if parent in exclude_dirnames:
        trace.append(f"Parent dir '{parent}' excluded")
        excluded = True

    if _matches_glob(exclude_globs, resolved):
        trace.append("Excluded by glob pattern")
        excluded = True

    # Check for overrides
    if excluded:
        if parent in include_dirnames:
            trace.append(f"Parent dir '{parent}' override")
            return True, trace
        if _matches_glob(include_globs, resolved):
            trace.append("Included by glob override")
            return True, trace
        return False, trace

    # Not excluded, no override needed
    return True, trace
