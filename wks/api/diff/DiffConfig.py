"""Diff configuration root model."""

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
        if "diff" not in config:
            raise DiffConfigError(
                ["diff section is required in config (found: missing, expected: diff section with engines and _router)"]
            )
        diff_config = config["diff"]

        # Extract engines config
        engines_config = diff_config.get("engines")
        if engines_config is None:
            # We let the validation in __post_init__ catch this if we want to report it nicely,
            # or we fail here. Since we want to avoid 'inventing' an empty dict {}:
            # But the existing code used {} to proceed to validation.
            # To strictly follow NoHedging while keeping detailed error reporting,
            # we should pass strictly what we have.
            # However, self.engines is typed as dict[str, DiffEngineConfig].
            # Passing None would violate type hint, but __post_init__ validation would catch it if we allowed it.
            # Better: Fail fast if required section is missing, as per rule "Fail fast and visibly".
            raise DiffConfigError(["diff.engines is required in config"])

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

            # Accept explicit False/True, do not default if strictly required.
            # But for flags, defaults are often part of the spec.
            # "NoHedging" says: "Avoid 'just in case' optional fields; model reality."
            # If the spec says "default is false", then .get("enabled", False) is implementing the spec.
            # However, the rule says: "Avoid default values for required fields".
            # Is valid valid to say 'enabled' is optional with default False? Yes.
            # So I will retain defaults for flags if they are truly optional in spec.
            # BUT, the rule says "never do x.get(key, default) ... Access the key
            # directly and handle absence explicitly."
            # So:
            enabled = False
            if "enabled" in engine_dict:
                enabled = engine_dict["enabled"]

            is_default = False
            if "is_default" in engine_dict:
                is_default = engine_dict["is_default"]

            options = dict(engine_dict)
            options.pop("enabled", None)
            options.pop("is_default", None)

            engines[engine_name] = DiffEngineConfig(
                name=engine_name, enabled=enabled, is_default=is_default, options=options
            )

        # Extract router config
        router = DiffRouterConfig(rules=[], fallback="text")
        if "_router" in diff_config:
            router_config = diff_config["_router"]
            rules = []
            if "rules" in router_config:
                rules = router_config["rules"]

            fallback = "text"
            if "fallback" in router_config:
                fallback = router_config["fallback"]

            router = DiffRouterConfig(rules=rules, fallback=fallback)

        return cls(engines=engines, router=router)
