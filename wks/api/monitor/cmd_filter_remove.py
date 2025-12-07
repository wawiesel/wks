"""Monitor filter-remove API function.

Remove a value from a monitor configuration list.
Matches CLI: wksc monitor filter remove <list-name> <value>, MCP: wksm_monitor_filter_remove
"""

from ..config.WKSConfig import WKSConfig
from ...utils import canonicalize_path
from ..base import StageResult
from .MonitorConfig import MonitorConfig


def cmd_filter_remove(list_name: str, value: str) -> StageResult:
    """Remove a value from a monitor configuration list."""

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    if list_name not in MonitorConfig.get_filter_list_names():
        raise ValueError(f"Unknown list_name: {list_name!r}")

    resolve_path = list_name in ("include_paths", "exclude_paths")
    value_resolved = canonicalize_path(value) if resolve_path else value.strip()

    items = getattr(monitor_cfg.filter, list_name)

    removed_value = None
    for idx, item in enumerate(list(items)):
        cmp_item = canonicalize_path(item) if resolve_path else item
        if cmp_item == value_resolved:
            removed_value = item
            del items[idx]
            break

    if removed_value is None:
        result = {
            "success": False,
            "message": f"Value not found in {list_name}: {value}",
            "not_found": True,
        }
        return StageResult(
            announce=f"Removing from {list_name}: {value}",
            result=str(result.get("message", "")),
            output=result,
            success=False,
        )

    config.save()
    result = {"success": True, "message": f"Removed from {list_name}: {removed_value}", "value_removed": removed_value}
    return StageResult(
        announce=f"Removing from {list_name}: {value}",
        result=str(result.get("message", "")),
        output=result,
    )
