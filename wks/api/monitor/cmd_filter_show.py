"""Monitor filter-show API function.

This function gets the contents of a monitor configuration list or, if no list
is specified, returns the available list names.
Matches CLI: wksc monitor filter show [<list-name>], MCP: wksm_monitor_filter_show
"""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import MonitorFilterShowOutput
from .MonitorConfig import MonitorConfig


def cmd_filter_show(list_name: str | None = None) -> StageResult:
    """Get contents of a monitor configuration list or list available names."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.3, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        if not isinstance(list_name, str) or not list_name:
            yield (0.6, "Listing available filter lists...")
            available_lists = list(MonitorConfig.get_filter_list_names())
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterShowOutput(
                errors=[],
                warnings=[],
                available_lists=available_lists,
                list_name=None,
                items=None,
                count=None,
                success=True,
                error=None,
            ).model_dump(mode="python")
            result_obj.result = "Available monitor lists"
            result_obj.success = True
            return

        if list_name not in MonitorConfig.get_filter_list_names():
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterShowOutput(
                errors=[],
                warnings=[],
                available_lists=None,
                list_name=None,
                items=None,
                count=None,
                success=False,
                error=f"Unknown list_name: {list_name!r}",
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["error"]
            result_obj.success = False
            raise ValueError(f"Unknown list_name: {list_name!r}")

        yield (0.7, f"Retrieving {list_name}...")
        items = list(getattr(monitor_cfg.filter, list_name))
        yield (1.0, "Complete")
        result_obj.output = MonitorFilterShowOutput(
            errors=[],
            warnings=[],
            available_lists=None,
            list_name=list_name,
            items=items,
            count=len(items),
            success=True,
            error=None,
        ).model_dump(mode="python")
        result_obj.result = f"Showing {list_name} ({len(items)} items)"
        result_obj.success = True

    announce = "Listing available monitor lists..." if not list_name else f"Showing {list_name}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
