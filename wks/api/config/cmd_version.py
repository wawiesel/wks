from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import ConfigVersionOutput
from .get_package_version import get_package_version


def cmd_version() -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.3, "Getting package version...")
        version = get_package_version()

        yield (1.0, "Complete")

        result_obj.result = f"WKS version: {version}"
        result_obj.output = ConfigVersionOutput(
            errors=[],
            warnings=[],
            version=version,
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Getting version information...",
        progress_callback=do_work,
    )
