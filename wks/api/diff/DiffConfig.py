"""Diff configuration root model (UNO: single model)."""

from dataclasses import dataclass

from .DiffConfigError import DiffConfigError
from .DiffEngineConfig import DiffEngineConfig
from .DiffRouterConfig import DiffRouterConfig


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
                "diff.engines must be a dict "
                "with at least one engine with is_default=true "
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
    def from_config_dict(cls, config: dict) -> "DiffConfig":
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
        fallback = router_config.get("fallback", "text")  # Default to "text" if not present

        router = DiffRouterConfig(rules=rules, fallback=fallback)

        return cls(engines=engines, router=router)
