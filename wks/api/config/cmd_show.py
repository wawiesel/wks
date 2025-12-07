"""Show configuration command."""

from collections.abc import Iterator

from ..base import StageResult
from .WKSConfig import WKSConfig


def cmd_show(section: str | None = None, show_all: bool = False) -> StageResult:
    """Show configuration sections, a specific section, or complete configuration.

    Args:
        section: Optional section name. If not provided and show_all=False, shows all section names.
        show_all: If True, returns complete configuration (for MCP wksm_config).

    Returns:
        StageResult with section names, section config data, or complete config
    """
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        """Do the actual work - generator that yields progress and updates result.
        
        Yields: (progress_percent: float, message: str) tuples
        Updates result_obj.result, result_obj.output, and result_obj.success before finishing.
        """
        yield (0.3, "Loading configuration...")
        config = WKSConfig.load()
        yield (0.6, "Processing sections...")
        config_dict = config.to_dict()

        # If show_all is True, return complete configuration (for MCP)
        if show_all:
            yield (0.9, "Serializing configuration...")
            yield (1.0, "Complete")
            result_obj.result = "Configuration loaded successfully"
            result_obj.output = config_dict
            result_obj.success = True
            return

        # Get available section names from WKSConfig dataclass fields
        available_sections = [field.name for field in config.__dataclass_fields__.values()]

        if section is None:
            # Show all section names
            yield (1.0, "Complete")
            result_obj.result = f"Found {len(available_sections)} section(s)"
            result_obj.output = {
                "sections": available_sections,
                "count": len(available_sections),
            }
            result_obj.success = True
            return

        # Show specific section
        if section not in available_sections:
            yield (1.0, "Complete")
            result_obj.result = f"Section '{section}' not found"
            result_obj.output = {
                "error": f"Unknown section: {section}",
                "available_sections": available_sections,
            }
            result_obj.success = False
            return

        # Get section data
        yield (0.9, "Retrieving section data...")
        section_data = config_dict.get(section)
        yield (1.0, "Complete")
        result_obj.result = f"Retrieved configuration for '{section}'"
        result_obj.output = section_data
        result_obj.success = True

    if show_all:
        announce_msg = "Loading complete configuration..."
    elif section is None:
        announce_msg = "Listing configuration sections..."
    else:
        announce_msg = f"Showing configuration for section '{section}'..."

    return StageResult(
        announce=announce_msg,
        progress_callback=do_work,
    )
