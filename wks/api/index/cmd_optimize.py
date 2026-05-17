from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import IndexOptimizeOutput


def cmd_optimize() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "Index not configured"
            result_obj.output = IndexOptimizeOutput(
                errors=["No index section in config"],
                warnings=[],
                search_index="",
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (0.5, "Creating search indexes...")
        from ._ChunkStore import _ChunkStore

        with Database(config.database, "index") as db:
            search_index = _ChunkStore(db).ensure_search_indexes()

        yield (1.0, "Complete")
        result_obj.result = f"Search index ready: {search_index}"
        result_obj.output = IndexOptimizeOutput(
            errors=[],
            warnings=[],
            search_index=search_index,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Optimizing index search...",
        progress_callback=do_work,
    )
