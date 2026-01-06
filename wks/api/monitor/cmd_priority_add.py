"""Monitor priority-add API function.

This function sets or updates the priority of a priority directory.
Matches CLI: wksc monitor priority add <path> <priority>, MCP: wksm_monitor_priority_add
"""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import MonitorPriorityAddOutput


def cmd_priority_add(path: str, priority: float) -> StageResult:
    """Set or update priority for a priority directory (creates if missing).

    Args:
        path: Directory path
        priority: New priority score

    Returns:
        StageResult with all 4 stages of data
    """

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        path_stored: str,
        new_priority: float,
        created: bool = False,
        already_exists: bool = False,
        old_priority: float | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorPriorityAddOutput(
            errors=[],
            warnings=[],
            success=success,
            message=message,
            path_stored=path_stored,
            new_priority=new_priority,
            created=created,
            already_exists=already_exists,
            old_priority=old_priority,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from wks.api.config.find_matching_path_key import find_matching_path_key
        from wks.api.config.normalize_path import normalize_path

        from ..config.WKSConfig import WKSConfig

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        # Resolve path
        yield (0.4, "Resolving path...")
        path_resolved = str(normalize_path(path))
        existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

        # If not present, create with given priority
        yield (0.6, "Updating priority...")
        if existing_key is None:
            config.monitor.priority.dirs[path_resolved] = priority
            _build_result(
                result_obj,
                success=True,
                message=f"Set priority for {path_resolved}: {priority} (created)",
                path_stored=path_resolved,
                new_priority=priority,
                created=True,
            )
        else:
            # Update existing priority
            old_priority = config.monitor.priority.dirs[existing_key]
            config.monitor.priority.dirs[existing_key] = priority
            _build_result(
                result_obj,
                success=True,
                message=f"Updated priority for {existing_key}: {old_priority} → {priority}",
                path_stored=existing_key,
                new_priority=priority,
                already_exists=True,
                old_priority=old_priority,
            )

        yield (0.8, "Saving configuration...")
        config.save()

        yield (1.0, "Complete")

    return StageResult(
        announce=f"Setting priority for priority directory: {path} to {priority}",
        progress_callback=do_work,
    )
