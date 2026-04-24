"""Cat command - retrieves cached content by checksum or path."""

from pathlib import Path

from wks.api.cat._format_target_for_display import format_target_for_display
from wks.services.cat import CatRequest, read_content

from ..config.StageResult import StageResult


def cmd(
    target: str,
    output_path: Path | None = None,
    engine: str | None = None,
) -> StageResult:
    """Retrieve content for a target (checksum, strict URI, or file path)."""
    display_target = format_target_for_display(target)

    def do_work(result_obj: StageResult):
        yield (0.2, "Resolving target...")
        response = read_content(CatRequest(target=target, output_path=output_path, engine=engine))
        yield (0.8, "Collecting content...")
        result_obj.output = response.model_dump(mode="python", exclude={"success", "message", "failure_kind"})
        if response.success:
            result_obj.result = "Retrieved content"
        else:
            result_obj.result = response.message
        result_obj.success = response.success
        yield (1.0, "Complete")

    return StageResult(
        announce=f"Retrieving content for {display_target}...",
        announce_segments=(
            ("Retrieving content for ", None),
            (display_target, "magenta"),
            ("...", None),
        ),
        progress_callback=do_work,
    )
