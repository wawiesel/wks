"""Monitor sync API function.

This function forces an update of a file or directory into the monitor database.
Matches CLI: wksc monitor sync <path> [--recursive], MCP tool: monitor_sync
"""

from collections.abc import Iterator

from wks.api.config.URI import URI

from ..config.StageResult import StageResult
from . import MonitorSyncOutput
from ._sync_uri import sync_uri_steps


def cmd_sync(
    uri: URI,
    recursive: bool = False,
) -> StageResult:
    """Force update of file or directory into monitor database.

    Args:
        uri: URI to sync (file://)
        recursive: Whether to recursively process directories

    Returns:
        StageResult with sync results (files_synced, files_skipped, errors)
    """

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        files_synced: int,
        files_skipped: int,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorSyncOutput(
            errors=errors or [],
            warnings=warnings or [],
            success=success,
            message=message,
            files_synced=files_synced,
            files_skipped=files_skipped,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()
        output = yield from sync_uri_steps(config, uri, recursive=recursive, write_status=True)
        _build_result(
            result_obj,
            success=output.success,
            message=output.message,
            files_synced=output.files_synced,
            files_skipped=output.files_skipped,
            errors=output.errors,
            warnings=output.warnings,
        )

    return StageResult(
        announce=f"Syncing {uri}...",
        progress_callback=do_work,
    )
