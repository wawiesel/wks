"""Show configuration command."""

import json
from typing import Any

import typer

from ..base import StageResult
from .WKSConfig import WKSConfig


def cmd_show(
    section: str | None = typer.Argument(None, help="Configuration section name (e.g., 'monitor', 'db', 'vault')"),
) -> StageResult:
    """Show configuration sections or a specific section.
    
    Args:
        section: Optional section name. If not provided, shows all section names.
    
    Returns:
        StageResult with section names or section config data
    """
    config = WKSConfig.load()
    config_dict = config.to_dict()
    
    # Get available section names from WKSConfig dataclass fields
    available_sections = [field.name for field in config.__dataclass_fields__.values()]
    
    if section is None:
        # Show all section names
        return StageResult(
            announce="Listing configuration sections...",
            result=f"Found {len(available_sections)} section(s)",
            output={
                "sections": available_sections,
                "count": len(available_sections),
            },
            success=True,
        )
    
    # Show specific section
    if section not in available_sections:
        return StageResult(
            announce=f"Showing configuration for section '{section}'...",
            result=f"Section '{section}' not found",
            output={
                "error": f"Unknown section: {section}",
                "available_sections": available_sections,
            },
            success=False,
        )
    
    # Get section data
    section_data = config_dict.get(section)
    
    return StageResult(
        announce=f"Showing configuration for section '{section}'...",
        result=f"Retrieved configuration for '{section}'",
        output={
            "section": section,
            "data": section_data,
        },
        success=True,
    )

