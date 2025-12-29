"""Transform command."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ...api.StageResult import StageResult
from ...utils.path_to_uri import path_to_uri
from ._get_controller import _get_controller
from ._TransformResult import _TransformResult


def cmd_transform(
    engine: str,
    file_path: Path,
    overrides: dict[str, Any],
    output: Path | None = None,
) -> StageResult:
    """Execute transform command.

    Args:
        engine: Engine name
        file_path: Source file path
        overrides: Configuration overrides
        output: Optional output path

    Returns:
        StageResult with TransformResult output
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Initializing controller...")

        try:
            with _get_controller() as controller:
                yield (0.3, "Transforming...")

                cache_key = controller.transform(file_path, engine, overrides, output)

                # Get cache location for destination_uri
                cache_location = controller.cache_manager.cache_dir / f"{cache_key}.md"
                if not cache_location.exists():
                    # Try to find with any extension
                    candidates = list(controller.cache_manager.cache_dir.glob(f"{cache_key}.*"))
                    cache_location = candidates[0] if candidates else cache_location

                yield (1.0, "Complete")

                result_data = _TransformResult(
                    source_uri=path_to_uri(file_path.absolute()),
                    destination_uri=path_to_uri(cache_location.absolute()),
                    engine=engine,
                    status="success",
                    checksum=cache_key,
                )

                result_obj.result = f"Transformed {file_path.name} ({cache_key[:8]})"
                result_obj.output = result_data.model_dump()
                result_obj.success = True

        except Exception as e:
            yield (1.0, "Failed")
            result_obj.result = str(e)
            result_obj.output = {"errors": [str(e)]}
            result_obj.success = False
            return

    return StageResult(
        announce=f"Transforming {file_path.name}...",
        progress_callback=do_work,
    )
