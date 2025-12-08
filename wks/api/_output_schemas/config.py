"""Output schemas for config commands."""

from typing import Any

from pydantic import Field

from ._base import BaseOutputSchema
from ._registry import register_output_schema


class ConfigShowOutput(BaseOutputSchema):
    """Output schema for config show command.

    Output structure:
    - errors: list[str] - list of error messages, empty list if no errors
    - warnings: list[str] - list of warning messages, empty list if no warnings
    - section: str - the section name, empty string if none provided (listing all sections)
    - content: dict[str, Any] - if section is empty, dict with "sections" key containing list of section names; if section provided, the section config dict
    - config_path: str - path to the configuration file
    """
    section: str = Field(..., description="Section name, empty string if none provided (listing all sections)")
    content: dict[str, Any] = Field(..., description="If section is empty: dict with 'sections' key containing list of section names; if section provided: the section config dict")
    config_path: str = Field(..., description="Path to the configuration file")


class ConfigVersionOutput(BaseOutputSchema):
    """Output schema for config version command."""
    version: str = Field(..., description="Package version string")
    git_sha: str = Field(..., description="Git commit SHA (short), empty string if not available")
    full_version: str = Field(..., description="Full version string (version + git_sha if available)")


# Register schemas
register_output_schema("config", "show", ConfigShowOutput)
register_output_schema("config", "version", ConfigVersionOutput)
