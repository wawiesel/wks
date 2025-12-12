"""Monitor filter-add API function.

Add a value to a monitor configuration list.
Matches CLI: wksc monitor filter add <list-name> <value>, MCP: wksm_monitor_filter_add
"""

from collections.abc import Iterator
from typing import Any

from ...utils import canonicalize_path
from ..config.WKSConfig import WKSConfig
from ..StageResult import StageResult
from . import MonitorFilterAddOutput
from ._validate_value import _validate_value
from .MonitorConfig import MonitorConfig


def cmd_filter_add(list_name: str, value: str) -> StageResult:
    """Add a value to a monitor configuration list."""

    def _build_result(
        result_obj: StageResult,
        success: bool,
        message: str,
        value_stored: str | None = None,
        validation_failed: bool = False,
        already_exists: bool = False,
        errors: list[str] | None = None,
    ) -> None:
        """Helper to build and assign the output result."""
        result_obj.output = MonitorFilterAddOutput(
            errors=errors or ([message] if not success and message else []),
            warnings=[],
            success=success,
            message=message,
            value_stored=value_stored,
            validation_failed=validation_failed,
            already_exists=already_exists,
        ).model_dump(mode="python")
        result_obj.result = message
        result_obj.success = success

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        if list_name not in MonitorConfig.get_filter_list_names():
            _build_result(
                result_obj,
                success=False,
                message=f"Unknown list_name: {list_name!r}",
                errors=[f"Unknown list_name: {list_name!r}"],
            )
            yield (1.0, "Complete")
            raise ValueError(f"Unknown list_name: {list_name!r}")

        yield (0.4, "Validating value...")
        value_to_store, error = _validate_value(list_name, value, monitor_cfg)

        if error:
            _build_result(
                result_obj,
                success=False,
                message=error,
                validation_failed=True,
            )
            yield (1.0, "Complete")
            return

        # Check duplicates
        yield (0.6, "Checking for duplicates...")
        resolve_path = list_name in ("include_paths", "exclude_paths")
        items = getattr(monitor_cfg.filter, list_name)

        # For paths, we compare canonicalized versions. For others, direct string comparison.
        # value_to_store is already normalized/canonicalized by _validate_value for paths.
        cmp_value = canonicalize_path(value_to_store) if resolve_path else value_to_store

        existing = None
        for item in items:
            cmp_item = canonicalize_path(item) if resolve_path else item
            if cmp_item == cmp_value:
                existing = item
                break

        if existing:
            _build_result(
                result_obj,
                success=False,
                message=f"Already in {list_name}: {existing}",
                already_exists=True,
            )
            yield (1.0, "Complete")
            return

        # Add and save
        yield (0.8, "Saving configuration...")
        items.append(value_to_store)
        config.save()

        _build_result(
            result_obj,
            success=True,
            message=f"Added to {list_name}: {value_to_store}",
            value_stored=value_to_store,
        )
        yield (1.0, "Complete")

    return StageResult(
        announce=f"Adding to {list_name}: {value}",
        progress_callback=do_work,
    )
