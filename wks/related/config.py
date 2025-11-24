"""Related (similarity) configuration dataclass with validation."""

from __future__ import annotations

__all__ = ["RelatedConfigError", "RelatedConfig", "RelatedEngineConfig", "RelatedRouterConfig"]

from dataclasses import dataclass
from typing import Any, Dict, List


class RelatedConfigError(Exception):
    """Raised when related configuration is invalid."""

    def __init__(self, errors: List[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Related configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class RelatedEngineConfig:
    """Related (similarity) engine-specific configuration."""

    name: str
    enabled: bool
    is_default: bool
    options: Dict[str, Any]

    def _validate_name(self) -> List[str]:
        """Validate engine name is a non-empty string."""
        errors = []

        if not isinstance(self.name, str) or not self.name:
            errors.append(
                f"related engine name must be a non-empty string "
                f"(found: {type(self.name).__name__} = {self.name!r}, "
                f"expected: string like 'embedding' or 'diff_based')"
            )

        return errors

    def _validate_enabled(self) -> List[str]:
        """Validate enabled is a boolean."""
        errors = []

        if not isinstance(self.enabled, bool):
            errors.append(
                f"related engine '{self.name}' enabled must be a boolean "
                f"(found: {type(self.enabled).__name__} = {self.enabled!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_is_default(self) -> List[str]:
        """Validate is_default is a boolean."""
        errors = []

        if not isinstance(self.is_default, bool):
            errors.append(
                f"related engine '{self.name}' is_default must be a boolean "
                f"(found: {type(self.is_default).__name__} = {self.is_default!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_options(self) -> List[str]:
        """Validate options is a dictionary."""
        errors = []

        if not isinstance(self.options, dict):
            errors.append(
                f"related engine '{self.name}' options must be a dict "
                f"(found: {type(self.options).__name__} = {self.options!r}, "
                f"expected: dict)"
            )

        return errors

    def __post_init__(self):
        """Validate related engine configuration after initialization."""
        errors = []
        errors.extend(self._validate_name())
        errors.extend(self._validate_enabled())
        errors.extend(self._validate_is_default())
        errors.extend(self._validate_options())

        if errors:
            raise RelatedConfigError(errors)


@dataclass
class RelatedRouterConfig:
    """Related router configuration for engine selection."""

    default: str
    rules: List[Dict[str, Any]]

    def _validate_default(self) -> List[str]:
        """Validate default is a non-empty string."""
        errors = []

        if not isinstance(self.default, str) or not self.default:
            errors.append(
                f"related._router.default must be a non-empty string "
                f"(found: {type(self.default).__name__} = {self.default!r}, "
                f"expected: engine name like 'embedding')"
            )

        return errors

    def _validate_rules(self) -> List[str]:
        """Validate rules is a list of dicts."""
        errors = []

        if not isinstance(self.rules, list):
            errors.append(
                f"related._router.rules must be a list "
                f"(found: {type(self.rules).__name__} = {self.rules!r}, "
                f"expected: list of routing rules)"
            )
            return errors

        for i, rule in enumerate(self.rules):
            if not isinstance(rule, dict):
                errors.append(
                    f"related._router.rules[{i}] must be a dict "
                    f"(found: {type(rule).__name__} = {rule!r}, "
                    f"expected: dict with 'engine' and routing conditions)"
                )

        return errors

    def __post_init__(self):
        """Validate related router configuration after initialization."""
        errors = []
        errors.extend(self._validate_default())
        errors.extend(self._validate_rules())

        if errors:
            raise RelatedConfigError(errors)


@dataclass
class RelatedConfig:
    """Related (similarity) configuration loaded from config dict with validation."""

    engines: Dict[str, RelatedEngineConfig]
    router: RelatedRouterConfig

    def _validate_engines(self) -> List[str]:
        """Validate engines configuration."""
        errors = []

        if not isinstance(self.engines, dict):
            errors.append(
                f"related.engines must be a dict "
                f"(found: {type(self.engines).__name__}, "
                f"expected: dict of engine configurations)"
            )
            return errors

        # Validate each engine config
        for name, engine in self.engines.items():
            if not isinstance(engine, RelatedEngineConfig):
                errors.append(
                    f"related.engines['{name}'] must be a RelatedEngineConfig instance "
                    f"(found: {type(engine).__name__}, "
                    f"expected: RelatedEngineConfig)"
                )

        # Check that at least one engine is marked as default
        default_engines = [name for name, eng in self.engines.items() if eng.is_default]
        if not default_engines:
            errors.append(
                "related.engines must have at least one engine with is_default=true "
                "(found: no default engines, expected: at least one is_default=true)"
            )

        return errors

    def _validate_router(self) -> List[str]:
        """Validate router configuration."""
        errors = []

        if not isinstance(self.router, RelatedRouterConfig):
            errors.append(
                f"related._router must be a RelatedRouterConfig instance "
                f"(found: {type(self.router).__name__}, "
                f"expected: RelatedRouterConfig)"
            )

        return errors

    def __post_init__(self):
        """Validate related configuration after initialization.

        Collects all validation errors and raises a single RelatedConfigError
        with all errors, so the user can see everything that needs fixing.
        """
        errors = []
        errors.extend(self._validate_engines())
        errors.extend(self._validate_router())

        if errors:
            raise RelatedConfigError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> "RelatedConfig":
        """Load related config from config dict.

        Args:
            config: Full WKS configuration dictionary

        Returns:
            RelatedConfig instance

        Raises:
            RelatedConfigError: If related section is missing or field values are invalid
        """
        related_config = config.get("related")
        if not related_config:
            raise RelatedConfigError([
                "related section is required in config "
                "(found: missing, expected: related section with engines and _router)"
            ])

        # Extract engines config
        engines_config = related_config.get("engines", {})
        engines = {}

        for engine_name, engine_dict in engines_config.items():
            if not isinstance(engine_dict, dict):
                raise RelatedConfigError([
                    f"related.engines['{engine_name}'] must be a dict "
                    f"(found: {type(engine_dict).__name__}, "
                    f"expected: dict with 'enabled', 'is_default', and optional options)"
                ])

            enabled = engine_dict.get("enabled", False)
            is_default = engine_dict.get("is_default", False)
            options = dict(engine_dict)
            options.pop("enabled", None)
            options.pop("is_default", None)

            engines[engine_name] = RelatedEngineConfig(
                name=engine_name,
                enabled=enabled,
                is_default=is_default,
                options=options
            )

        # Extract router config
        router_config = related_config.get("_router", {})
        default = router_config.get("default", "")
        rules = router_config.get("rules", [])

        router = RelatedRouterConfig(
            default=default,
            rules=rules
        )

        return cls(engines=engines, router=router)
