"""Monitor filter-add API function.

Add a value to a monitor configuration list.
Matches CLI: wksc monitor filter add <list-name> <value>, MCP: wksm_monitor_filter_add
"""

from collections.abc import Iterator
from pathlib import Path

from ..StageResult import StageResult
from .._output_schemas.monitor import MonitorFilterAddOutput
from .MonitorConfig import MonitorConfig


def cmd_filter_add(list_name: str, value: str) -> StageResult:
    """Add a value to a monitor configuration list."""
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result."""
        from ..config.WKSConfig import WKSConfig
        from ...utils import canonicalize_path

        yield (0.2, "Loading configuration...")
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        if list_name not in MonitorConfig.get_filter_list_names():
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterAddOutput(
                errors=[],
                warnings=[],
                success=False,
                message=f"Unknown list_name: {list_name!r}",
                value_stored=None,
                validation_failed=None,
                already_exists=None,
                error=f"Unknown list_name: {list_name!r}",
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            raise ValueError(f"Unknown list_name: {list_name!r}")

        resolve_path = list_name in ("include_paths", "exclude_paths")

        # Normalize and validate
        yield (0.4, "Validating value...")
        if resolve_path:
            value_resolved = canonicalize_path(value)
            home_dir = str(Path.home())
            value_to_store = (
                "~" + value_resolved[len(home_dir) :] if value_resolved.startswith(home_dir) else value_resolved
            )
        elif list_name in ("include_dirnames", "exclude_dirnames"):
            # Validate directory name
            entry = value.strip()
            if not entry:
                err = "Directory name cannot be empty"
            elif any(ch in entry for ch in "*?[]"):
                err = "Directory names cannot contain wildcard characters"
            elif "/" in entry or "\\" in entry:
                err = "Directory names cannot contain path separators"
            else:
                opposite = "exclude_dirnames" if list_name == "include_dirnames" else "include_dirnames"
                if entry in getattr(monitor_cfg.filter, opposite):
                    err = f"Directory name '{entry}' already present in {opposite}"
                else:
                    err = None

            if err:
                yield (1.0, "Complete")
                result_obj.output = MonitorFilterAddOutput(
                    errors=[],
                    warnings=[],
                    success=False,
                    message=err,
                    value_stored=None,
                    validation_failed=True,
                    already_exists=None,
                    error=None,
                ).model_dump(mode="python")
                result_obj.result = err
                result_obj.success = False
                return
            value_resolved = entry
            value_to_store = value_resolved
        elif list_name in ("include_globs", "exclude_globs"):
            # Validate glob pattern
            import fnmatch

            entry = value.strip()
            if not entry:
                err = "Glob pattern cannot be empty"
            else:
                try:
                    fnmatch.fnmatch("test", entry)
                    err = None
                except Exception as exc:  # pragma: no cover - defensive
                    err = f"Invalid glob syntax: {exc}"

            if err:
                yield (1.0, "Complete")
                result_obj.output = MonitorFilterAddOutput(
                    errors=[],
                    warnings=[],
                    success=False,
                    message=err,
                    value_stored=None,
                    validation_failed=True,
                    already_exists=None,
                    error=None,
                ).model_dump(mode="python")
                result_obj.result = err
                result_obj.success = False
                return
            value_resolved = entry
            value_to_store = value_resolved
        else:
            value_resolved = value
            value_to_store = value

        # Check duplicates
        yield (0.6, "Checking for duplicates...")
        items = getattr(monitor_cfg.filter, list_name)
        existing = None
        for item in items:
            cmp_item = canonicalize_path(item) if resolve_path else item
            cmp_value = canonicalize_path(value_resolved) if resolve_path else value_resolved
            if cmp_item == cmp_value:
                existing = item
                break

        if existing:
            yield (1.0, "Complete")
            result_obj.output = MonitorFilterAddOutput(
                errors=[],
                warnings=[],
                success=False,
                message=f"Already in {list_name}: {existing}",
                value_stored=None,
                validation_failed=None,
                already_exists=True,
                error=None,
            ).model_dump(mode="python")
            result_obj.result = result_obj.output["message"]
            result_obj.success = False
            return

        # Add and save
        yield (0.8, "Saving configuration...")
        items.append(value_to_store)
        config.save()

        yield (1.0, "Complete")
        result_obj.output = MonitorFilterAddOutput(
            errors=[],
            warnings=[],
            success=True,
            message=f"Added to {list_name}: {value_to_store}",
            value_stored=value_to_store,
            validation_failed=None,
            already_exists=None,
            error=None,
        ).model_dump(mode="python")
        result_obj.result = result_obj.output["message"]
        result_obj.success = True

    return StageResult(
        announce=f"Adding to {list_name}: {value}",
        progress_callback=do_work,
    )
