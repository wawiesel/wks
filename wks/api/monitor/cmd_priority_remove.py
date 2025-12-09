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
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig
        from ...utils import canonicalize_path, find_matching_path_key

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        if not config.monitor.priority.dirs:
            yield (1.0, "Complete")
            result_obj.output = MonitorPriorityRemoveOutput(
                errors=[],
                warnings=[],
                success=False,
                message="No priority directories configured",
                path_removed=None,
                priority=None,
                not_found=True,
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            return

        # Resolve path
        yield (0.4, "Resolving path...")
        path_resolved = canonicalize_path(path)
        existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

        # Check if exists
        yield (0.6, "Checking if priority directory exists...")
        if existing_key is None:
            yield (1.0, "Complete")
            result_obj.output = MonitorPriorityRemoveOutput(
                errors=[],
                warnings=[],
                success=False,
                message=f"Not a priority directory: {path_resolved}",
                path_removed=None,
                priority=None,
                not_found=True,
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            return

        # Get priority before removing
        priority = config.monitor.priority.dirs[existing_key]

        # Remove from priority directories
        yield (0.8, "Removing priority directory...")
        del config.monitor.priority.dirs[existing_key]

        yield (0.9, "Saving configuration...")
        config.save()

        yield (1.0, "Complete")
        result_obj.output = MonitorPriorityRemoveOutput(
            errors=[],
            warnings=[],
            success=True,
            message=f"Removed priority directory: {existing_key}",
            path_removed=existing_key,
            priority=priority,
            not_found=None,
        ).model_dump(mode="python")
        result_obj.result = result_obj.output["message"]
        result_obj.success = True

    return StageResult(
        announce=f"Removing priority directory: {path}",
        progress_callback=do_work,
    )
