"""Transform configuration root model (UNO: single model)."""

from dataclasses import dataclass

from .CacheConfig import CacheConfig
from .EngineConfig import EngineConfig
from .TransformConfigError import TransformConfigError


@dataclass
class TransformConfig:
    """Transform configuration loaded from config dict with validation."""

    cache: CacheConfig
    engines: dict[str, EngineConfig]
    database: str
    default_engine: str = "docling"

    def _validate_cache(self) -> list[str]:
        """Validate cache configuration."""
        errors: list[str] = []

        if not isinstance(self.cache, CacheConfig):
            errors.append(
                f"transform.cache must be a CacheConfig instance "
                f"(found: {type(self.cache).__name__}, "
                f"expected: CacheConfig)"
            )

        return errors

    def _validate_engines(self) -> list[str]:
        """Validate engines configuration."""
        errors: list[str] = []

        if not isinstance(self.engines, dict):
            errors.append(
                f"transform.engines must be a dict "
                f"(found: {type(self.engines).__name__}, "
                f"expected: dict of engine configurations)"
            )
            return errors

        # Validate each engine config
        for name, engine in self.engines.items():
            if not isinstance(engine, EngineConfig):
                errors.append(
                    f"transform.engines['{name}'] must be an EngineConfig instance "
                    f"(found: {type(engine).__name__}, "
                    f"expected: EngineConfig)"
                )

        return errors

    def __post_init__(self):
        """Validate transform configuration after initialization.

        Collects all validation errors and raises a single TransformConfigError
        with all errors, so the user can see everything that needs fixing.
        """
        errors: list[str] = []
        errors.extend(self._validate_cache())
        errors.extend(self._validate_engines())

        if errors:
            raise TransformConfigError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> "TransformConfig":
        """Load transform config from config dict.

        Args:
            config: Full WKS configuration dictionary

        Returns:
            TransformConfig instance

        Raises:
            TransformConfigError: If transform section is missing or field values are invalid
        """
        transform_config = config.get("transform")
        if not transform_config:
            raise TransformConfigError(
                [
                    "transform section is required in config "
                    "(found: missing, expected: transform section with cache and engines)"
                ]
            )

        database = transform_config.get("database", "wks_transform")

        # Extract cache config
        cache_config = transform_config.get("cache", {})
        cache_location = cache_config.get("location", ".wks/transform/cache")
        max_size_bytes = cache_config.get("max_size_bytes", 1073741824)  # 1GB default

        cache = CacheConfig(location=cache_location, max_size_bytes=max_size_bytes)

        # Extract engines config
        engines_config = transform_config.get("engines", {})
        engines = {}

        for engine_name, engine_dict in engines_config.items():
            if not isinstance(engine_dict, dict):
                raise TransformConfigError(
                    [
                        f"transform.engines['{engine_name}'] must be a dict "
                        f"(found: {type(engine_dict).__name__}, "
                        f"expected: dict with 'enabled' and optional options)"
                    ]
                )

            enabled = engine_dict.get("enabled", False)
            options = dict(engine_dict)
            options.pop("enabled", None)  # Remove 'enabled' from options

            engines[engine_name] = EngineConfig(name=engine_name, enabled=enabled, options=options)

        default_engine = transform_config.get("default_engine", "docling")

        return cls(cache=cache, engines=engines, database=database, default_engine=default_engine)
