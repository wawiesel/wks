"""Transform command."""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ...api.StageResult import StageResult
from ...api.URI import URI
from . import TransformEngineOutput
from ._get_controller import _get_controller


def cmd_engine(
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

                # Measure processing time
                start_time = time.time()
                gen = controller.transform(file_path, engine, overrides, output)
                try:
                    while True:
                        msg = next(gen)
                        yield (0.5, msg)
                except StopIteration as e:
                    cache_key, cached = e.value

                processing_time_ms = int((time.time() - start_time) * 1000)

                # Get cache location for destination_uri
                cache_location = controller.cache_manager.cache_dir / f"{cache_key}.md"
                if not cache_location.exists():
                    # Try to find with any extension
                    candidates = list(controller.cache_manager.cache_dir.glob(f"{cache_key}.*"))
                    cache_location = candidates[0] if candidates else cache_location

                # Read content if output is not set (typical CLI behavior might want preview?)
                # Or just leave None. Schema requires the field, but value can be None
                # if defined as Optional in Pydantic?
                # The schema validation error said "Field required", implying missing key.
                # TransformTransformOutput schema definition: "output_content": {"type": "string"} -- wait.
                # If schema has "type": "string" without "null", it cannot be None.
                # Let's check schema definition again.
                # In turn 1 (view_file schema), lines 35: "type": "string".
                # If the Pydantic model generated from schema doesn't allow None, we must send empty string.
                # But the error object sent `output_content: null` and that seemingly passed (or failed?).
                # Wait, step 3653 failed manually. Then step 3663 passed.
                # Step 3662 used `None`. `test_cmd_transform_error_structure` asserted `is None`.
                # If Pydantic model allows None, then None is fine.
                # `_TransformResult` defines `str | None`.

                output_content = None
                # If the user wants content printed to stdout (maybe via another flag? or just always None for now)
                # The CLI usually saves to file.

                yield (1.0, "Complete")

                result_obj.result = f"Transformed {file_path.name} ({cache_key[:8]})"
                result_obj.output = TransformEngineOutput(
                    source_uri=str(URI.from_path(file_path)),
                    destination_uri=str(URI.from_path(cache_location)),
                    engine=engine,
                    status="success",
                    checksum=cache_key,
                    output_content=output_content,
                    processing_time_ms=processing_time_ms,
                    cached=cached,
                    errors=[],
                    warnings=[],
                ).model_dump(mode="python")
                result_obj.success = True

        except Exception as e:
            yield (1.0, "Failed")
            result_obj.result = str(e)
            result_obj.output = TransformEngineOutput(
                source_uri=str(URI.from_path(file_path)),
                destination_uri="",
                engine=engine,
                status="error",
                checksum="",
                output_content=None,
                processing_time_ms=0,
                cached=False,
                errors=[str(e)],
                warnings=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

    return StageResult(
        announce=f"Transforming {file_path.name}...",
        progress_callback=do_work,
    )
