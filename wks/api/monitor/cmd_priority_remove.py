"""Monitor priority-remove API function.

This function removes a priority directory.
Matches CLI: wksc monitor priority remove <path>, MCP: wksm_monitor_priority_remove
"""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import MonitorPriorityRemoveOutput


def cmd_priority_remove(path: str) -> StageResult:
    """Remove a priority directory.

    Args:
        path: Directory path to remove

    Returns:
        StageResult with all 4 stages of data
    """

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        path_removed: str | None = None,
        priority: float | None = None,
        not_found: bool | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorPriorityRemoveOutput(
            errors=[],
            warnings=[],
            success=success,
            message=message,
            path_removed=path_removed,
            priority=priority,
            not_found=not_found,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from wks.api.config.canonicalize_path import canonicalize_path
        from wks.api.config.find_matching_path_key import find_matching_path_key

        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        if not config.monitor.priority.dirs:
            _build_result(
                result_obj,
                success=False,
                message="No priority directories configured",
                not_found=True,
            )
            yield (1.0, "Complete")
            return

        # Resolve path
        yield (0.4, "Resolving path...")
        path_resolved = canonicalize_path(path)
        existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

        # Check if exists
        yield (0.6, "Checking if priority directory exists...")
        if existing_key is None:
            _build_result(
                result_obj,
                success=False,
                message=f"Not a priority directory: {path_resolved}",
                not_found=True,
            )
            yield (1.0, "Complete")
            return

        # Get priority before removing
        priority = config.monitor.priority.dirs[existing_key]

        # Remove from priority directories
        yield (0.8, "Removing priority directory...")
        del config.monitor.priority.dirs[existing_key]

        yield (0.9, "Saving configuration...")
        config.save()

        _build_result(
            result_obj,
            success=True,
            message=f"Removed priority directory: {existing_key}",
            path_removed=existing_key,
            priority=priority,
        )
        yield (1.0, "Complete")

    return StageResult(
        announce=f"Removing priority directory: {path}",
        progress_callback=do_work,
    )
