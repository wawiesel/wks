"""List configuration sections command."""

from collections.abc import Iterator

from ..StageResult import StageResult
from . import ConfigListOutput
from .load_config_with_output import load_config_with_output


def cmd_list() -> StageResult:
    """List all configuration section names."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.3, "Loading configuration...")
        config, error_output = load_config_with_output("", ConfigListOutput)
        if error_output is not None:
            yield (1.0, "Complete")
            result_obj.result = "Configuration validation failed"
            result_obj.output = error_output
            result_obj.success = False
            return

        yield (0.6, "Collecting sections...")
        config_dict = config.to_dict()
        sections = list(config_dict.keys())

        yield (1.0, "Complete")
        result_obj.result = f"Found {len(sections)} section(s)"
        result_obj.output = ConfigListOutput(
            errors=[],
            warnings=[],
            section="",
            content={"sections": sections},
            config_path=str(config.path),
        ).model_dump(mode="python")
        result_obj.success = True

    return StageResult(
        announce="Listing configuration sections...",
        progress_callback=do_work,
    )
