"""Cat command - retrieves cached content by checksum or path."""

from pathlib import Path
from typing import Any

from ...api.StageResult import StageResult
from ..transform.get_content import get_content


def cmd_cat(
    target: str,
    output_path: Path | None = None,
) -> StageResult:
    """Retrieve content for a target (checksum or file path).

    Args:
        target: Checksum (64 hex chars) or file path
        output_path: Optional output file path

    Returns:
        StageResult with content in 'content' field of output
    """

    def do_work(result_obj: StageResult) -> Any:
        yield (0.1, "Retrieving content...")

        try:
            content = get_content(target, output_path)

            result_obj.output = {
                "content": content,
                "target": target,
                "output_path": str(output_path) if output_path else None,
            }
            result_obj.result = f"Retrieved content for {target[:8]}..."
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
