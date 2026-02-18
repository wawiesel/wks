"""Show index status."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import IndexStatusOutput


def cmd_status(name: str = "") -> StageResult:
    """Show statistics for a named index, or all indexes."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "Index not configured"
            result_obj.output = IndexStatusOutput(
                errors=["No index section in config"],
                warnings=[],
                indexes={},
            ).model_dump(mode="python")
            result_obj.success = False
            return

        from ._ChunkStore import _ChunkStore

        with Database(config.database, "index") as db:
            store = _ChunkStore(db)

            yield (0.5, "Counting...")
            indexes_to_check = [name] if name else list(config.index.indexes.keys())
            index_stats: dict[str, dict] = {}

            for idx_name in indexes_to_check:
                chunk_count = store.count(idx_name)
                uris = store.uris(idx_name)
                index_stats[idx_name] = {
                    "document_count": len(uris),
                    "chunk_count": chunk_count,
                    "uris": uris,
                }

            yield (1.0, "Complete")
            total_docs = sum(s["document_count"] for s in index_stats.values())
            total_chunks = sum(s["chunk_count"] for s in index_stats.values())
            result_obj.result = f"{len(index_stats)} indexes, {total_docs} documents, {total_chunks} chunks"
            result_obj.output = IndexStatusOutput(
                errors=[],
                warnings=[],
                indexes=index_stats,
            ).model_dump(mode="python")
            result_obj.success = True

    return StageResult(
        announce="Checking index...",
        progress_callback=do_work,
    )
