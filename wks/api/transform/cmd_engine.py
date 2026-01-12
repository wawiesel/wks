"""Transform command."""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..config._ensure_arg_uri import _ensure_arg_uri
from ..config.StageResult import StageResult
from ..config.URI import URI
from . import MAX_GENERATOR_ITERATIONS, TransformEngineOutput
from ._get_controller import _get_controller


def cmd_engine(
    engine: str,
    uri: URI,
    overrides: dict[str, Any],
    output: Path | None = None,
) -> StageResult:
    """Execute transform command.

    Args:
        engine: Engine name
        uri: Source URI
        overrides: Configuration overrides
        output: Optional output path

    Returns:
        StageResult with TransformResult output
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Initializing controller...")

        yield (0.2, "Resolving path...")
        file_path = _ensure_arg_uri(
            uri,
            result_obj,
            TransformEngineOutput,
            uri_field="source_uri",
            destination_uri="",
            engine=engine,
            status="error",
            checksum="",
            output_content=None,
            processing_time_ms=0,
            cached=False,
            warnings=[],
        )
        if not file_path:
            return

        try:
            with _get_controller() as controller:
                yield (0.3, "Transforming...")

                # Measure processing time
                start_time = time.time()
                gen = controller.transform(file_path, engine, overrides, output)
                try:
                    for _ in range(MAX_GENERATOR_ITERATIONS):
                        msg = next(gen)
                        yield (0.5, msg)
                    # Loop completed - check if generator is actually exhausted
                    # If next() raises StopIteration, we're done; otherwise we hit the limit
                    next(gen)
                    raise RuntimeError("Transform generator exceeded MAX_GENERATOR_ITERATIONS")
                except StopIteration as e:
                    cache_key, cached = e.value

                processing_time_ms = int((time.time() - start_time) * 1000)

                # Get cache location for destination_uri
                cache_location = controller.cache_manager.cache_dir / f"{cache_key}.md"
                if not cache_location.exists():
                    # Try to find with any extension
                    candidates = list(controller.cache_manager.cache_dir.glob(f"{cache_key}.*"))
                    cache_location = candidates[0] if candidates else cache_location

                output_content = None

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
        announce=f"Transforming {uri}...",
        progress_callback=do_work,
    )
