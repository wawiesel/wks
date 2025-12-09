"""Monitor priority-add API function.

This function sets or updates the priority of a priority directory.
Matches CLI: wksc monitor priority add <path> <priority>, MCP: wksm_monitor_priority_add
"""

from collections.abc import Iterator

from ..StageResult import StageResult
from .._output_schemas.monitor import MonitorPriorityAddOutput


def cmd_priority_add(path: str, priority: float) -> StageResult:
    """Set or update priority for a priority directory (creates if missing).

    Args:
        path: Directory path
        priority: New priority score

    Returns:
        StageResult with all 4 stages of data
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig
        from ...utils import canonicalize_path, find_matching_path_key

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()

        # Resolve path
        yield (0.4, "Resolving path...")
        path_resolved = canonicalize_path(path)
        existing_key = find_matching_path_key(config.monitor.priority.dirs, path_resolved)

        # If not present, create with given priority
        yield (0.6, "Updating priority...")
        if existing_key is None:
            config.monitor.priority.dirs[path_resolved] = priority
            result_obj.output = MonitorPriorityAddOutput(
                errors=[],
                warnings=[],
                success=True,
                message=f"Set priority for {path_resolved}: {priority} (created)",
                path_stored=path_resolved,
                new_priority=priority,
                created=True,
                already_exists=False,
                old_priority=None,
            ).model_dump(mode="python")
        else:
            # Update existing priority
            old_priority = config.monitor.priority.dirs[existing_key]
            config.monitor.priority.dirs[existing_key] = priority
            result_obj.output = MonitorPriorityAddOutput(
                errors=[],
                warnings=[],
                success=True,
                message=f"Updated priority for {existing_key}: {old_priority} → {priority}",
                path_stored=existing_key,
                new_priority=priority,
                created=False,
                already_exists=True,
                old_priority=old_priority,
            ).model_dump(mode="python")

        yield (0.8, "Saving configuration...")
        config.save()

        yield (1.0, "Complete")
        result_obj.result = result_obj.output["message"]
        result_obj.success = True

    return StageResult(
        announce=f"Setting priority for priority directory: {path} to {priority}",
        progress_callback=do_work,
    )
