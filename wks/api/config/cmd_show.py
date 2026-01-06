"""Show configuration command."""

from collections.abc import Iterator

from ..config.StageResult import StageResult
from . import ConfigShowOutput
from .load_config_with_output import load_config_with_output


def cmd_show(section: str) -> StageResult:
    """Show a specific configuration section."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.3, "Loading configuration...")
        config, error_output = load_config_with_output(section, ConfigShowOutput)
        if error_output is not None:
            yield (1.0, "Complete")
            result_obj.result = "Configuration validation failed"
            result_obj.output = error_output
            result_obj.success = False
            return
        assert config is not None  # If error_output is None, config must be set
        yield (0.6, "Processing sections...")
        config_dict = config.to_dict()
        available_sections = list(config_dict.keys())
        all_errors: list[str] = []
        all_warnings: list[str] = []

        if section not in available_sections:
            all_errors.append(f"Unknown section: {section}")
            yield (1.0, "Complete")
            result_obj.result = f"Section '{section}' not found"
            result_obj.output = ConfigShowOutput(
                errors=all_errors,
                warnings=all_warnings,
                section=section,
                content={},
                config_path=str(config.path),
            ).model_dump(mode="python")
            result_obj.success = False
            return

        yield (1.0, "Complete")
        result_obj.result = f"Retrieved configuration for '{section}'"
        result_obj.output = ConfigShowOutput(
            errors=all_errors,
            warnings=all_warnings,
            section=section,
            content=config_dict[section],
            config_path=str(config.path),
        ).model_dump(mode="python")
        result_obj.success = True

    announce = f"Showing configuration for section '{section}'..."
    return StageResult(announce=announce, progress_callback=do_work)
