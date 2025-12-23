"""Diff router configuration (UNO: single model)."""

from dataclasses import dataclass
from typing import Any

from .DiffConfigError import DiffConfigError


@dataclass
class DiffRouterConfig:
    """Diff router configuration for engine selection."""

    rules: list[dict[str, Any]]
    fallback: str

    def _validate_rules(self) -> list[str]:
        """Validate rules is a list of dicts."""
        errors: list[str] = []

        if not isinstance(self.rules, list):
            errors.append(
                f"diff._router.rules must be a list "
                f"(found: {type(self.rules).__name__} = {self.rules!r}, "
                f"expected: list of routing rules)"
            )
            return errors

        for i, rule in enumerate(self.rules):
            if not isinstance(rule, dict):
                errors.append(
                    f"diff._router.rules[{i}] must be a dict "
                    f"(found: {type(rule).__name__} = {rule!r}, "
                    f"expected: dict with 'engine' and routing conditions)"
                )

        return errors

    def _validate_fallback(self) -> list[str]:
        """Validate fallback is a non-empty string."""
        errors: list[str] = []

        if not isinstance(self.fallback, str) or not self.fallback:
            errors.append(
                f"diff._router.fallback must be a non-empty string "
                f"(found: {type(self.fallback).__name__} = {self.fallback!r}, "
                f"expected: engine name like 'bdiff')"
            )

        return errors

    def __post_init__(self):
        """Validate diff router configuration after initialization."""
        errors: list[str] = []
        errors.extend(self._validate_rules())
        errors.extend(self._validate_fallback())

        if errors:
            raise DiffConfigError(errors)
