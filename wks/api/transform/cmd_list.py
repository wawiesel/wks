"""List available transform engines command."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import TransformListOutput


def cmd_list() -> StageResult:
    """List all available transform engines."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.5, "Loading configuration...")
        config = WKSConfig.load()
        engines = config.transform.engines

        engine_data = {}
        for name, engine_config in engines.items():
            engine_data[name] = {
                "type": engine_config.type,
                "supported_types": engine_config.supported_types or ["*"],
            }

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(engines)} engine(s)"
        result_obj.output = TransformListOutput(
            errors=[],
            warnings=[],
            engines=engine_data,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing transform engines...",
        progress_callback=do_work,
    )
