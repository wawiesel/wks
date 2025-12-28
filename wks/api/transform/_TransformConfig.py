"""Transform configuration root model."""

from dataclasses import dataclass

from ._CacheConfig import _CacheConfig
from ._EngineConfig import _EngineConfig
from ._TransformConfigError import _TransformConfigError


@dataclass
class _TransformConfig:
    """Transform configuration loaded from config dict with validation."""

    cache: _CacheConfig
    engines: dict[str, _EngineConfig]

    def _validate_cache(self) -> list[str]:
        """Validate cache configuration."""
        errors: list[str] = []

        if not isinstance(self.cache, _CacheConfig):
            errors.append(
                f"transform.cache must be a _CacheConfig instance "
                f"(found: {type(self.cache).__name__}, "
                f"expected: _CacheConfig)"
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
            if not isinstance(engine, _EngineConfig):
                errors.append(
                    f"transform.engines['{name}'] must be an _EngineConfig instance "
                    f"(found: {type(engine).__name__}, "
                    f"expected: _EngineConfig)"
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
            raise _TransformConfigError(errors)

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
            raise _TransformConfigError(
                [
                    "transform section is required in config "
                    "(found: missing, expected: transform section with cache and engines)"
                ]
            )



        # Extract cache config
        cache_config = transform_config.get("cache", {})
        cache_base_dir = cache_config.get("base_dir", "~/_transform")
        max_size_bytes = cache_config.get("max_size_bytes", 1073741824)  # 1GB default

        cache = _CacheConfig(base_dir=cache_base_dir, max_size_bytes=max_size_bytes)

        # Extract engines config
        engines_config = transform_config.get("engines", {})
        engines = {}

        for engine_name, engine_dict in engines_config.items():
            if not isinstance(engine_dict, dict):
                raise _TransformConfigError(
                    [
                        f"transform.engines['{engine_name}'] must be a dict "
                        f"(found: {type(engine_dict).__name__}, "
                        f"expected: dict with 'enabled' and optional options)"
                    ]
                )


            engine_type = engine_dict.get("type")
            if not engine_type:
                 raise _TransformConfigError(
                    [
                        f"transform.engines['{engine_name}'] missing required 'type' field"
                    ]
                )

            data = engine_dict.get("data", {})
            if not isinstance(data, dict):
                 raise _TransformConfigError(
                    [
                        f"transform.engines['{engine_name}'].data must be a dict"
                    ]
                )

            engines[engine_name] = _EngineConfig(name=engine_name, type=engine_type, data=data)

        return cls(cache=cache, engines=engines)
