"""Index a URI into a named index."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from ..database.Database import Database
from . import IndexOutput


def cmd(name: str, uri: str) -> StageResult:
    """Transform, chunk, and store a document in a named index."""
    uri = str(uri)

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.05, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "Index not configured"
            result_obj.output = IndexOutput(
                errors=["No index section in config"],
                warnings=[],
                index_name=name,
                uri=uri,
                chunk_count=0,
                checksum="",
            ).model_dump(mode="python")
            result_obj.success = False
            return

        if name not in config.index.indexes:
            yield (1.0, "Complete")
            result_obj.result = f"Unknown index: {name}"
            result_obj.output = IndexOutput(
                errors=[f"Index '{name}' not defined in config (available: {list(config.index.indexes.keys())})"],
                warnings=[],
                index_name=name,
                uri=uri,
                chunk_count=0,
                checksum="",
            ).model_dump(mode="python")
            result_obj.success = False
            return

        spec = config.index.indexes[name]

        # Resolve URI to file path
        from ..config.normalize_path import normalize_path

        file_path = normalize_path(uri)
        if not file_path.exists():
            yield (1.0, "Complete")
            result_obj.result = f"File not found: {file_path}"
            result_obj.output = IndexOutput(
                errors=[f"File not found: {file_path}"],
                warnings=[],
                index_name=name,
                uri=uri,
                chunk_count=0,
                checksum="",
            ).model_dump(mode="python")
            result_obj.success = False
            return

        # Transform
        from ..config.URI import URI
        from ..transform.cmd_engine import cmd_engine

        file_uri = URI.from_path(file_path)
        yield (0.1, f"Transforming with {spec.engine}...")

        res = cmd_engine(spec.engine, file_uri, {})
        for progress, msg in res.progress_callback(res):
            yield (0.1 + progress * 0.5, msg)

        if not res.success:
            yield (1.0, "Complete")
            result_obj.result = f"Transform failed: {res.result}"
            result_obj.output = IndexOutput(
                errors=[f"Transform failed: {res.result}"],
                warnings=[],
                index_name=name,
                uri=uri,
                chunk_count=0,
                checksum="",
            ).model_dump(mode="python")
            result_obj.success = False
            return

        cache_key = res.output["checksum"]

        # Read content from cache
        yield (0.65, "Reading content...")
        from ..transform.get_content import get_content

        content = get_content(cache_key)

        # Chunk
        yield (0.75, "Chunking...")
        from ._ChunkStore import _ChunkStore
        from ._SlidingWindowChunker import _SlidingWindowChunker

        chunker = _SlidingWindowChunker(spec.max_tokens, spec.overlap_tokens)
        chunks = chunker.chunk(content, str(file_uri))

        # Store
        yield (0.85, "Storing chunks...")
        with Database(config.database, "index") as db:
            store = _ChunkStore(db)
            store.replace_uri(name, str(file_uri), cache_key, chunks)

        yield (1.0, "Complete")
        result_obj.result = f"Indexed {file_path.name} into '{name}' ({len(chunks)} chunks)"
        result_obj.output = IndexOutput(
            errors=[],
            warnings=[],
            index_name=name,
            uri=str(file_uri),
            chunk_count=len(chunks),
            checksum=cache_key,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Indexing {uri}...",
        progress_callback=do_work,
    )
