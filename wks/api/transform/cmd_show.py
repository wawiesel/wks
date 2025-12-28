"""Show transform record command."""

from collections.abc import Iterator

from ...api.StageResult import StageResult
from ._get_controller import _get_controller


def cmd_show(checksum: str, content: bool = False) -> StageResult:
    """Show details of a transform.

    Args:
        checksum: Transform checksum
        content: Whether to include full content

    Returns:
        StageResult with record details
    """

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Initializing...")
        
        try:
            with _get_controller() as controller:
                yield (0.5, "Fetching record...")
                
                record = controller.get_record(checksum)
                if not record:
                    raise ValueError(f"No record found for checksum {checksum}")
                
                data = record.to_dict()
                if "_id" in data:
                    del data["_id"]
                    
                if content:
                    yield (0.8, "Fetching content...")
                    data["content"] = controller.get_content(checksum)

                yield (1.0, "Complete")
                result_obj.result = f"Record found for {checksum[:8]}"
                result_obj.output = data
                result_obj.success = True
                
        except Exception as e:
            yield (1.0, "Failed")
            result_obj.result = str(e)
            result_obj.success = False

    return StageResult(
        announce=f"Fetching transform {checksum[:8]}...",
        progress_callback=do_work,
    )
