"""Auto-index a URI into all indexes whose min_priority threshold is met."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from ..config.WKSConfig import WKSConfig
from . import IndexAutoOutput


def cmd_auto(uri: str) -> StageResult:
    """Index a URI into all matching indexes based on file priority."""
    uri = str(uri)

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.05, "Loading configuration...")
        config = WKSConfig.load()

        if config.index is None:
            yield (1.0, "Complete")
            result_obj.result = "No index configuration"
            result_obj.output = IndexAutoOutput(
                errors=[],
                warnings=[],
                uri=uri,
                priority=0.0,
                indexed=[],
                skipped=[],
            ).model_dump(mode="python")
            result_obj.success = True
            return

        # Resolve to path for priority calculation
        from ..config.normalize_path import normalize_path
        from ..monitor.calculate_priority import calculate_priority

        yield (0.1, "Calculating priority...")
        file_path = normalize_path(uri)
        if not file_path.exists():
            yield (1.0, "Complete")
            result_obj.result = f"File not found: {file_path}"
            result_obj.output = IndexAutoOutput(
                errors=[f"File not found: {file_path}"],
                warnings=[],
                uri=uri,
                priority=0.0,
                indexed=[],
                skipped=[],
            ).model_dump(mode="python")
            result_obj.success = False
            return

        monitor_cfg = config.monitor
        priority = calculate_priority(
            file_path,
            monitor_cfg.priority.dirs,
            monitor_cfg.priority.weights.model_dump(),
        )

        indexed: list[dict] = []
        skipped: list[str] = []
        errors: list[str] = []

        index_names = list(config.index.indexes.keys())
        for i, index_name in enumerate(index_names):
            spec = config.index.indexes[index_name]
            progress = 0.2 + (i / max(len(index_names), 1)) * 0.7

            if priority < spec.min_priority:
                skipped.append(index_name)
                yield (progress, f"Skipping '{index_name}' (priority {priority:.1f} < {spec.min_priority:.1f})")
                continue

            yield (progress, f"Indexing into '{index_name}'...")
            from .cmd import cmd as index_cmd

            res = index_cmd(index_name, uri)
            list(res.progress_callback(res))

            if res.success:
                indexed.append(
                    {
                        "index_name": index_name,
                        "chunk_count": res.output.get("chunk_count", 0),
                        "checksum": res.output.get("checksum", ""),
                    }
                )
            else:
                errors.append(f"Index '{index_name}': {res.result}")

        yield (1.0, "Complete")
        n = len(indexed)
        result_obj.result = f"Auto-indexed into {n} index(es)" if n > 0 else "No indexes matched"
        result_obj.output = IndexAutoOutput(
            errors=errors,
            warnings=[],
            uri=uri,
            priority=priority,
            indexed=indexed,
            skipped=skipped,
        ).model_dump(mode="python")
        result_obj.success = len(errors) == 0

    return StageResult(
        announce=f"Auto-indexing {uri}...",
        progress_callback=do_work,
    )
