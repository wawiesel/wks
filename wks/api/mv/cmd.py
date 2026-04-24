from collections.abc import Iterator

from wks.services.mv import MoveRequest, move_document

from ..config.StageResult import StageResult
from ..config.URI import URI
from . import MvMvOutput


def cmd(source: URI | str, dest: URI | str) -> StageResult:
    source_arg = str(source)
    dest_arg = str(dest)

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.2, "Validating move request...")
        response = move_document(MoveRequest(source=source_arg, dest=dest_arg))
        yield (0.8, "Finalizing move result...")
        yield (1.0, "Complete")
        result_obj.output = MvMvOutput(
            errors=response.errors,
            warnings=response.warnings,
            source=response.source,
            destination=response.destination,
            database_updated=response.database_updated,
            success=response.success,
        ).model_dump(mode="python")
        result_obj.result = response.message
        result_obj.success = response.success

    return StageResult(
        announce=f"Moving {source} to {dest}...",
        progress_callback=do_work,
    )
