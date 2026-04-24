"""Shared configuration read services."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from wks.api.config.WKSConfig import WKSConfig

from ._models import ServiceResponse


class ConfigSectionsResponse(ServiceResponse):
    """Config sections listing."""

    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    config_path: str
    sections: list[str] = Field(default_factory=list)


class ConfigSectionResponse(ServiceResponse):
    """One config section payload."""

    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    config_path: str
    section: str
    content: dict[str, Any] = Field(default_factory=dict)


def list_config_sections(*, config: WKSConfig | None = None) -> ConfigSectionsResponse:
    """List available config sections."""
    loaded_config = config or WKSConfig.load()
    config_dict = loaded_config.to_dict()
    return ConfigSectionsResponse(
        success=True,
        message=f"Found {len(config_dict)} section(s)",
        errors=[],
        warnings=[],
        config_path=str(loaded_config.path),
        sections=list(config_dict.keys()),
    )


def show_config_section(section: str, *, config: WKSConfig | None = None) -> ConfigSectionResponse:
    """Return one config section."""
    loaded_config = config or WKSConfig.load()
    config_dict = loaded_config.to_dict()
    if section not in config_dict:
        return ConfigSectionResponse(
            success=False,
            message=f"Section '{section}' not found",
            failure_kind="not_found",
            errors=[f"Unknown section: {section}"],
            warnings=[],
            config_path=str(loaded_config.path),
            section=section,
            content={},
        )
    return ConfigSectionResponse(
        success=True,
        message=f"Retrieved configuration for '{section}'",
        errors=[],
        warnings=[],
        config_path=str(loaded_config.path),
        section=section,
        content=config_dict[section],
    )
