"""Diff configuration dataclass with validation."""

from __future__ import annotations

__all__ = ["DiffConfig", "DiffConfigError", "DiffEngineConfig", "DiffRouterConfig"]

from dataclasses import dataclass
from typing import Any


class DiffConfigError(Exception):
    """Raised when diff configuration is invalid."""

    def __init__(self, errors: list[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Diff configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class DiffEngineConfig:
    """Diff engine-specific configuration."""

    name: str
    enabled: bool
    is_default: bool
    options: dict[str, Any]

    def _validate_name(self) -> list[str]:
        """Validate engine name is a non-empty string."""
        errors: list[str] = []

        if not isinstance(self.name, str) or not self.name:
            errors.append(
                f"diff engine name must be a non-empty string "
                f"(found: {type(self.name).__name__} = {self.name!r}, "
                f"expected: string like 'bdiff' or 'text')"
            )

        return errors

    def _validate_enabled(self) -> list[str]:
        """Validate enabled is a boolean."""
        errors: list[str] = []

        if not isinstance(self.enabled, bool):
            errors.append(
                f"diff engine '{self.name}' enabled must be a boolean "
                f"(found: {type(self.enabled).__name__} = {self.enabled!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_is_default(self) -> list[str]:
        """Validate is_default is a boolean."""
        errors: list[str] = []

        if not isinstance(self.is_default, bool):
            errors.append(
                f"diff engine '{self.name}' is_default must be a boolean "
                f"(found: {type(self.is_default).__name__} = {self.is_default!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_options(self) -> list[str]:
        """Validate options is a dictionary."""
        errors: list[str] = []

        if not isinstance(self.options, dict):
            errors.append(
                f"diff engine '{self.name}' options must be a dict "
                f"(found: {type(self.options).__name__} = {self.options!r}, "
                f"expected: dict)"
            )

        return errors

    def __post_init__(self):
        """Validate diff engine configuration after initialization."""
        errors: list[str] = []
        errors.extend(self._validate_name())
        errors.extend(self._validate_enabled())
        errors.extend(self._validate_is_default())
        errors.extend(self._validate_options())

        if errors:
            raise DiffConfigError(errors)


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


@dataclass
class DiffConfig:
    """Diff configuration loaded from config dict with validation."""

    engines: dict[str, DiffEngineConfig]
    router: DiffRouterConfig

    def _validate_engines(self) -> list[str]:
        """Validate engines configuration."""
        errors: list[str] = []

        if not isinstance(self.engines, dict):
            errors.append(
                f"diff.engines must be a dict "
                f"(found: {type(self.engines).__name__}, "
                f"expected: dict of engine configurations)"
            )
            return errors

        # Validate each engine config
        for name, engine in self.engines.items():
            if not isinstance(engine, DiffEngineConfig):
                errors.append(
                    f"diff.engines['{name}'] must be a DiffEngineConfig instance "
                    f"(found: {type(engine).__name__}, "
                    f"expected: DiffEngineConfig)"
                )

        # Check that at least one engine is marked as default
        default_engines = [name for name, eng in self.engines.items() if eng.is_default]
        if not default_engines:
            errors.append(
                "diff.engines must have at least one engine with is_default=true "
                "(found: no default engines, expected: at least one is_default=true)"
            )

        return errors

    def _validate_router(self) -> list[str]:
        """Validate router configuration."""
        errors: list[str] = []

        if not isinstance(self.router, DiffRouterConfig):
            errors.append(
                f"diff._router must be a DiffRouterConfig instance "
                f"(found: {type(self.router).__name__}, "
                f"expected: DiffRouterConfig)"
            )

        return errors

    def __post_init__(self):
        """Validate diff configuration after initialization.

        Collects all validation errors and raises a single DiffConfigError
        with all errors, so the user can see everything that needs fixing.
        """
        errors: list[str] = []
        errors.extend(self._validate_engines())
        errors.extend(self._validate_router())

        if errors:
            raise DiffConfigError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> DiffConfig:
        """Load diff config from config dict.

        Args:
            config: Full WKS configuration dictionary

        Returns:
            DiffConfig instance

        Raises:
            DiffConfigError: If diff section is missing or field values are invalid
        """
        diff_config = config.get("diff")
        if not diff_config:
            raise DiffConfigError(
                ["diff section is required in config (found: missing, expected: diff section with engines and _router)"]
            )

        # Extract engines config
        engines_config = diff_config.get("engines", {})
        engines = {}

        for engine_name, engine_dict in engines_config.items():
            if not isinstance(engine_dict, dict):
                raise DiffConfigError(
                    [
                        f"diff.engines['{engine_name}'] must be a dict "
                        f"(found: {type(engine_dict).__name__}, "
                        f"expected: dict with 'enabled', 'is_default', and optional options)"
                    ]
                )

            enabled = engine_dict.get("enabled", False)
            is_default = engine_dict.get("is_default", False)
            options = dict(engine_dict)
            options.pop("enabled", None)
            options.pop("is_default", None)

            engines[engine_name] = DiffEngineConfig(
                name=engine_name, enabled=enabled, is_default=is_default, options=options
            )

        # Extract router config
        router_config = diff_config.get("_router", {})
        rules = router_config.get("rules", [])
        fallback = router_config.get("fallback", "")

        router = DiffRouterConfig(rules=rules, fallback=fallback)

        return cls(engines=engines, router=router)
