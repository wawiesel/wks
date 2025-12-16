"""Explain why a path is allowed or excluded by monitor rules."""

from pathlib import Path

from ..config.WKSConfig import WKSConfig
from ._evaluate_roots import _evaluate_roots
from .matches_glob import matches_glob
from .MonitorConfig import MonitorConfig


def explain_path(cfg: MonitorConfig, path: Path) -> tuple[bool, list[str]]:
    """Explain why a path is allowed or excluded."""
    trace: list[str] = []
    # Use absolute() instead of resolve() to preserve symlinks
    # This allows monitoring symlinks that point outside the monitor root
    # and ensures we exclude symlinks residing IN .wks
    resolved = path.expanduser().absolute()

    # Check if path is within WKS home directory (automatically excluded)
    wks_home = WKSConfig.get_home_dir()
    try:
        # Check against wks_home. We accept that wks_home might be resolved,
        # but 'resolved' (the file) is absolute-unresolved.
        # This correctly catches files physically inside ~/.wks structure.
        if resolved == wks_home or resolved.is_relative_to(wks_home):
            trace.append(f"In WKS home directory {wks_home} (automatically ignored)")
            return False, trace
    except ValueError:
        pass

    # Normalize filter lists
    # Use absolute() to match the behavior above
    include_roots = [Path(p).expanduser().absolute() for p in cfg.filter.include_paths]
    exclude_roots = [Path(p).expanduser().absolute() for p in cfg.filter.exclude_paths]
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
    excluded = False

    # Check all path parts for excluded dirnames
    # We check the file name itself (if it's a directory effectively) and all parents
    # But for a file, we usually only care if it's INSIDE an excluded directory
    # The config name is 'exclude_dirnames', so we should check if any PARENT matches

    for p in resolved.parents:
        if p.name in exclude_dirnames:
            trace.append(f"Parent dir '{p.name}' excluded")
            excluded = True
            break

    if not excluded and resolved.name in exclude_dirnames:
        # Also check the name itself, in case we are asking about a directory
        trace.append(f"Directory '{resolved.name}' excluded")
        excluded = True

    if not excluded and matches_glob(exclude_globs, resolved):
        trace.append("Excluded by glob pattern")
        excluded = True

    # Check for overrides
    if excluded:
        # Check if any parent satisfies include_dirnames (nested include)
        # Strategy: Search from closest parent up to root
        # If we hit an include_dirname BEFORE hitting the exclude_dirname that banned us, we are good?
        # The current config structure is simple lists.
        # For now, let's keep the override logic simple: if immediate parent or glob matches include.
        # But this might be insufficient for deep nesting.
        # Given the "junk" issue, strict exclusion is better.

        parent = resolved.parent.name if resolved.parent != resolved else ""
        if parent in include_dirnames:
            trace.append(f"Parent dir '{parent}' override")
            return True, trace

        if matches_glob(include_globs, resolved):
            trace.append("Included by glob override")
            return True, trace
        return False, trace

    # Not excluded, no override needed
    return True, trace
