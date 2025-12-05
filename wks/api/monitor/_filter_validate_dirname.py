"""Validation for directory-name entries in monitor filter lists."""


def _filter_validate_dirname(entry: str, list_name: str, monitor_cfg) -> str | None:
    """Validate a directory name for monitor filters."""
    entry = entry.strip()
    if not entry:
        return "Directory name cannot be empty"
    if any(ch in entry for ch in "*?[]"):
        return "Directory names cannot contain wildcard characters"
    if "/" in entry or "\\" in entry:
        return "Directory names cannot contain path separators"
    opposite = "exclude_dirnames" if list_name == "include_dirnames" else "include_dirnames"
    if entry in getattr(monitor_cfg, opposite):
        return f"Directory name '{entry}' already present in {opposite}"
    return None
