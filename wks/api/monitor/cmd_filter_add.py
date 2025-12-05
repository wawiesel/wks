"""Monitor filter-add API function.

Add a value to a monitor configuration list.
Matches CLI: wksc monitor filter add <list-name> <value>, MCP: wksm_monitor_filter_add
"""

from pathlib import Path

import typer

from ...config import WKSConfig
from ...utils import canonicalize_path
from ..base import StageResult
from ._LIST_NAMES import _LIST_NAMES
from ._filter_validate_dirname import _filter_validate_dirname
from ._filter_validate_glob import _filter_validate_glob


def cmd_filter_add(
    list_name: str = typer.Argument(..., help="Name of list to modify"),
    value: str = typer.Argument(..., help="Value to add"),
) -> StageResult:
    """Add a value to a monitor configuration list."""

    config = WKSConfig.load()
    monitor_cfg = config.monitor

    if list_name not in _LIST_NAMES:
        raise ValueError(f"Unknown list_name: {list_name!r}")

    resolve_path = list_name in ("include_paths", "exclude_paths")

    # Normalize and validate
    if resolve_path:
        value_resolved = canonicalize_path(value)
        home_dir = str(Path.home())
        value_to_store = "~" + value_resolved[len(home_dir) :] if value_resolved.startswith(home_dir) else value_resolved
    elif list_name in ("include_dirnames", "exclude_dirnames"):
        err = _filter_validate_dirname(value, list_name, monitor_cfg)
        if err:
            result = {"success": False, "message": err, "validation_failed": True}
            return StageResult(announce=f"Adding to {list_name}: {value}", result=err, output=result, success=False)
        value_resolved = value.strip()
        value_to_store = value_resolved
    elif list_name in ("include_globs", "exclude_globs"):
        err = _filter_validate_glob(value)
        if err:
            result = {"success": False, "message": err, "validation_failed": True}
            return StageResult(announce=f"Adding to {list_name}: {value}", result=err, output=result, success=False)
        value_resolved = value.strip()
        value_to_store = value_resolved
    else:
        value_resolved = value
        value_to_store = value

    # Check duplicates
    existing = None
    for item in getattr(monitor_cfg, list_name):
        cmp_item = canonicalize_path(item) if resolve_path else item
        cmp_value = canonicalize_path(value_resolved) if resolve_path else value_resolved
        if cmp_item == cmp_value:
            existing = item
            break

    if existing:
        result = {"success": False, "message": f"Already in {list_name}: {existing}", "already_exists": True}
        return StageResult(
            announce=f"Adding to {list_name}: {value}",
            result=str(result.get("message", "")),
            output=result,
            success=False,
        )

    # Add and save
    getattr(monitor_cfg, list_name).append(value_to_store)
    config.save()

    result = {"success": True, "message": f"Added to {list_name}: {value_to_store}", "value_stored": value_to_store}
    return StageResult(
        announce=f"Adding to {list_name}: {value}",
        result=str(result.get("message", "")),
        output=result,
    )
