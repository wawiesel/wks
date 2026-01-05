"""Cat command - retrieves cached content by checksum or path."""

from pathlib import Path
from typing import Any

from ...api.StageResult import StageResult
from ..transform.get_content import get_content


def cmd(
    target: str,
    output_path: Path | None = None,
    engine: str | None = None,
) -> StageResult:
    """Retrieve content for a target (checksum or file path).

    Args:
        target: Checksum (64 hex chars) or file path
        output_path: Optional output file path
        engine: Optional engine override

    Returns:
        StageResult with content in 'content' field of output
    """

    def do_work(result_obj: StageResult) -> Any:
        from ..config.WKSConfig import WKSConfig
        from ..transform.cmd_engine import cmd_engine
        from ._is_checksum import _is_checksum
        from ._select_engine import _select_engine

        yield (0.1, f"Processing target: {target}")

        try:
            config = WKSConfig.load()
            cache_key = target

            # If not a checksum, it must be a path that needs transforming
            if not _is_checksum(target):
                from wks.api.config.normalize_path import normalize_path

                file_path = normalize_path(target)
                if not file_path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                selected_engine = _select_engine(file_path, engine, config)
                yield (0.2, f"Transforming {file_path.name} using {selected_engine}...")

                from ..URI import URI

                # Run transform
                res_transform = cmd_engine(selected_engine, URI.from_path(file_path), {})
                # Proxy progress from transform
                for progress, msg in res_transform.progress_callback(res_transform):
                    # Scale transform progress (0.0-1.0) to (0.2-0.8)
                    scaled_progress = 0.2 + (progress * 0.6)
                    yield (scaled_progress, msg)

                if not res_transform.success:
                    raise RuntimeError(f"Transform failed: {res_transform.result}")

                cache_key = res_transform.output["checksum"]

            yield (0.9, "Retrieving content from cache...")
            content = get_content(cache_key, output_path)

            result_obj.output = {
                "content": content,
                "target": target,
                "checksum": cache_key,
                "output_path": str(output_path) if output_path else None,
            }
            result_obj.result = f"Retrieved content for {target}"
            result_obj.success = True
            yield (1.0, "Complete")

        except Exception as e:
            result_obj.result = str(e)
            result_obj.success = False
            yield (1.0, "Failed")

    return StageResult(
        announce=f"Retrieving content for {target}...",
        progress_callback=do_work,
    )
