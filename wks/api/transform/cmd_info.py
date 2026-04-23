"""Show transform engine information command."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import TransformInfoOutput
from ._RouteEngineConfig import _RouteEngineConfig


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
            result_obj.output = TransformInfoOutput(
                errors=[f"Engine '{engine}' not found. Available: {list(engines.keys())}"],
                warnings=[],
                engine=engine,
                config={},
            ).model_dump(mode="python")
            result_obj.success = False
            return

        engine_config = engines[engine]

        yield (1.0, "Complete")
        result_obj.result = f"Engine: {engine}"
        if isinstance(engine_config, _RouteEngineConfig):
            config_output = {
                "type": engine_config.type,
                "order": engine_config.data.order,
                "passthrough_text": engine_config.data.passthrough_text,
                "reject_binary": engine_config.data.reject_binary,
            }
        else:
            config_output = {
                "type": engine_config.type,
                "supported_types": engine_config.supported_types or ["*"],
                "options": engine_config.data,
            }
        result_obj.output = TransformInfoOutput(
            errors=[],
            warnings=[],
            engine=engine,
            config=config_output,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce=f"Getting info for {engine}...",
        progress_callback=do_work,
    )
