"""Monitor filter-remove API function.

Remove a value from a monitor configuration list.
Matches CLI: wksc monitor filter remove <list-name> <value>, MCP: wksm_monitor_filter_remove
"""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import MonitorFilterRemoveOutput
from .MonitorConfig import MonitorConfig


def cmd_filter_remove(list_name: str, value: str) -> StageResult:
    """Remove a value from a monitor configuration list."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig
        from ...utils import canonicalize_path

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        if list_name not in MonitorConfig.get_filter_list_names():
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterRemoveOutput(
                errors=[f"Unknown list_name: {list_name!r}"],
                warnings=[],
                success=False,
                message=f"Unknown list_name: {list_name!r}",
                value_removed=None,
                not_found=False,
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            raise ValueError(f"Unknown list_name: {list_name!r}")

        yield (0.4, "Resolving value...")
        resolve_path = list_name in ("include_paths", "exclude_paths")
        value_resolved = canonicalize_path(value) if resolve_path else value.strip()

        yield (0.6, "Searching for value...")
        items = getattr(monitor_cfg.filter, list_name)

        removed_value = None
        for idx, item in enumerate(list(items)):
            cmp_item = canonicalize_path(item) if resolve_path else item
            if cmp_item == value_resolved:
                removed_value = item
                del items[idx]
                break

        if removed_value is None:
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterRemoveOutput(
                errors=[],
                warnings=[],
                success=False,
                message=f"Value not found in {list_name}: {value}",
                value_removed=None,
                not_found=True,
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            return

        yield (0.8, "Saving configuration...")
        config.save()
        yield (1.0, "Complete")
        result_obj.output = MonitorFilterRemoveOutput(
            errors=[],
            warnings=[],
            success=True,
            message=f"Removed from {list_name}: {removed_value}",
            value_removed=removed_value,
            not_found=False,
        ).model_dump(mode="python")
        result_obj.result = result_obj.output["message"]
        result_obj.success = True

    return StageResult(
        announce=f"Removing from {list_name}: {value}",
        progress_callback=do_work,
    )
