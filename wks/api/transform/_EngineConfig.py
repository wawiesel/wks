"""Engine configuration."""

from dataclasses import dataclass
from typing import Any

from ._TransformConfigError import _TransformConfigError


@dataclass
class _EngineConfig:
    """Engine-specific configuration."""


    name: str # The key from the engines dict
    type: str # The value of the "type" field
    data: dict[str, Any] # The value of the "data" field

    def _validate_name(self) -> list[str]:
        """Validate engine name is a non-empty string."""
        errors: list[str] = []

        if not isinstance(self.name, str) or not self.name:
            errors.append(
                f"engine name must be a non-empty string "
                f"(found: {type(self.name).__name__} = {self.name!r})"
            )

        return errors

    def _validate_type(self) -> list[str]:
        """Validate engine type is a non-empty string."""
        errors: list[str] = []

        if not isinstance(self.type, str) or not self.type:
            errors.append(
                f"engine '{self.name}' type must be a non-empty string "
                f"(found: {type(self.type).__name__} = {self.type!r}, "
                f"expected: string like 'docling')"
            )

        return errors

    def _validate_data(self) -> list[str]:
        """Validate data is a dictionary."""
        errors: list[str] = []

        if not isinstance(self.data, dict):
            errors.append(
                f"engine '{self.name}' data must be a dict "
                f"(found: {type(self.data).__name__} = {self.data!r}, "
                f"expected: dict)"
            )

        return errors

    def __post_init__(self):
        """Validate engine configuration after initialization."""
        errors: list[str] = []
        errors.extend(self._validate_name())
        errors.extend(self._validate_type())
        errors.extend(self._validate_data())

        if errors:
            raise _TransformConfigError(errors)
