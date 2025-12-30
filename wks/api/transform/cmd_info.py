"""Show transform engine information command."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import TransformInfoOutput


def cmd_info(engine: str) -> StageResult:
    """Show details for a specific transform engine."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.5, "Loading configuration...")
        config = WKSConfig.load()
        engines = config.transform.engines

        if engine not in engines:
            yield (1.0, "Failed")
            result_obj.result = f"Engine '{engine}' not found"
            result_obj.success = False
            return

        engine_config = engines[engine]

        yield (1.0, "Complete")
        result_obj.result = f"Engine: {engine}"
        result_obj.output = TransformInfoOutput(
            errors=[],
            warnings=[],
            engine=engine,
            config={
                "type": engine_config.type,
                "supported_types": engine_config.supported_types or ["*"],
                "options": engine_config.data,
            },
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Getting info for {engine}...",
        progress_callback=do_work,
    )
