"""Engine configuration (UNO: single model)."""

from dataclasses import dataclass
from typing import Any

from .TransformConfigError import TransformConfigError


@dataclass
class EngineConfig:
    """Engine-specific configuration."""

    name: str
    enabled: bool
    options: dict[str, Any]

    def _validate_name(self) -> list[str]:
        """Validate engine name is a non-empty string."""
        errors: list[str] = []

        if not isinstance(self.name, str) or not self.name:
            errors.append(
                f"engine name must be a non-empty string "
                f"(found: {type(self.name).__name__} = {self.name!r}, "
                f"expected: string like 'docling')"
            )

        return errors

    def _validate_enabled(self) -> list[str]:
        """Validate enabled is a boolean."""
        errors: list[str] = []

        if not isinstance(self.enabled, bool):
            errors.append(
                f"engine '{self.name}' enabled must be a boolean "
                f"(found: {type(self.enabled).__name__} = {self.enabled!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_options(self) -> list[str]:
        """Validate options is a dictionary."""
        errors: list[str] = []

        if not isinstance(self.options, dict):
            errors.append(
                f"engine '{self.name}' options must be a dict "
                f"(found: {type(self.options).__name__} = {self.options!r}, "
                f"expected: dict)"
            )

        return errors

    def __post_init__(self):
        """Validate engine configuration after initialization."""
        errors: list[str] = []
        errors.extend(self._validate_name())
        errors.extend(self._validate_enabled())
        errors.extend(self._validate_options())

        if errors:
            raise TransformConfigError(errors)
