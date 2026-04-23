"""List available transform engines command."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import TransformListOutput
from ._RouteEngineConfig import _RouteEngineConfig


def cmd_list() -> StageResult:
    """List all available transform engines."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.5, "Loading configuration...")
        config = WKSConfig.load()
        engines = config.transform.engines

        engine_data = {}
        for name, engine_config in engines.items():
            if isinstance(engine_config, _RouteEngineConfig):
                engine_data[name] = {
                    "type": engine_config.type,
                    "order": engine_config.data.order,
                    "passthrough_text": engine_config.data.passthrough_text,
                    "reject_binary": engine_config.data.reject_binary,
                }
            else:
                engine_data[name] = {
                    "type": engine_config.type,
                    "supported_types": engine_config.supported_types or ["*"],
                }

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(engines)} engine(s)"
        result_obj.output = TransformListOutput(
            errors=[],
            warnings=[],
            default_engine=config.transform.default_engine,
            engines=engine_data,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing transform engines...",
        progress_callback=do_work,
    )
