"""Show configuration command."""

from collections.abc import Iterator

from ..StageResult import StageResult
from .WKSConfig import WKSConfig


def cmd_show(section: str = "") -> StageResult:
    """Show configuration section or list all sections.

    Args:
        section: Section name. Empty string lists all section names, otherwise returns specific section.
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.3, "Loading configuration...")
        config = WKSConfig.load()
        yield (0.6, "Processing sections...")
        config_dict = config.to_dict()
        available_sections = list(config_dict.keys())
        all_errors: list[str] = []
        all_warnings: list[str] = []

        if section == "":
            yield (1.0, "Complete")
            result_obj.result = f"Found {len(available_sections)} section(s)"
            result_obj.output = {
                "errors": all_errors,
                "warnings": all_warnings,
                "section": "",
                "content": {"sections": available_sections},
                "config_path": str(config.path),
            }
            result_obj.success = len(all_errors) == 0
            return

        if section not in available_sections:
            all_errors.append(f"Unknown section: {section}")
            yield (1.0, "Complete")
            result_obj.result = f"Section '{section}' not found"
            result_obj.output = {
                "errors": all_errors,
                "warnings": all_warnings,
                "section": section,
                "content": {},
                "config_path": str(config.path),
            }
            result_obj.success = False
            return

        yield (1.0, "Complete")
        result_obj.result = f"Retrieved configuration for '{section}'"
        result_obj.output = {
            "errors": all_errors,
            "warnings": all_warnings,
            "section": section,
            "content": config_dict.get(section, {}),
            "config_path": str(config.path),
        }
        result_obj.success = len(all_errors) == 0

    announce = "Listing configuration sections..." if section == "" else f"Showing configuration for section '{section}'..."
    return StageResult(announce=announce, progress_callback=do_work)
