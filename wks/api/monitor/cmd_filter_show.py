"""Monitor filter-show API function.

This function gets the contents of a monitor configuration list or, if no list
is specified, returns the available list names.
Matches CLI: wksc monitor filter show [<list-name>], MCP: wksm_monitor_filter_show
"""

from collections.abc import Iterator
from typing import Any

from ..StageResult import StageResult
from . import MonitorFilterShowOutput
from .MonitorConfig import MonitorConfig


def cmd_filter_show(list_name: str | None = None) -> StageResult:
    """Get contents of a monitor configuration list or list available names."""

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        available_lists: list[str],
        items: list[str],
        list_name_out: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorFilterShowOutput(
            errors=errors or ([message] if not success and message else []),
            warnings=[],
            available_lists=available_lists,
            list_name=list_name_out,
            items=items,
            count=len(items) if items else 0,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.3, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        if not isinstance(list_name, str) or not list_name:
            yield (0.6, "Listing available filter lists...")
            available_lists = list(MonitorConfig.get_filter_list_names())
            _build_result(
                result_obj,
                success=True,
                message="Available monitor lists",
                available_lists=available_lists,
                items=[],
            )
            yield (1.0, "Complete")
            return

        if list_name not in MonitorConfig.get_filter_list_names():
            available_lists = list(MonitorConfig.get_filter_list_names())
            _build_result(
                result_obj,
                success=False,
                message=f"Unknown list_name: {list_name!r}",
                available_lists=available_lists,
                items=[],
                errors=[f"Unknown list_name: {list_name!r}"],
            )
            yield (1.0, "Complete")
            raise ValueError(f"Unknown list_name: {list_name!r}")

        yield (0.7, f"Retrieving {list_name}...")
        items = list(getattr(monitor_cfg.filter, list_name))
        available_lists = list(MonitorConfig.get_filter_list_names())
        
        _build_result(
            result_obj,
            success=True,
            message=f"Showing {list_name} ({len(items)} items)",
            available_lists=available_lists,
            items=items,
            list_name_out=list_name,
        )
        yield (1.0, "Complete")

    announce = "Listing available monitor lists..." if not list_name else f"Showing {list_name}..."
    return StageResult(
        announce=announce,
        progress_callback=do_work,
    )
