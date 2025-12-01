"""Transform configuration dataclass with validation."""

from __future__ import annotations

__all__ = ["TransformConfigError", "TransformConfig", "CacheConfig", "EngineConfig"]

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


class TransformConfigError(Exception):
    """Raised when transform configuration is invalid."""

    def __init__(self, errors: List[str]):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = errors
        message = "Transform configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class CacheConfig:
    """Cache configuration for transformed files."""

    location: str
    max_size_bytes: int

    def _validate_cache_location(self) -> List[str]:
        """Validate cache location is a non-empty string or Path."""
        errors = []

        if not isinstance(self.location, (str, Path)) or not str(self.location):
            errors.append(
                f"transform.cache.location must be a non-empty string or Path "
                f"(found: {type(self.location).__name__} = {self.location!r}, "
                f"expected: path string like '.wks/transform/cache')"
            )

        return errors

    def _validate_max_size(self) -> List[str]:
        """Validate max_size_bytes is a positive integer."""
        errors = []

        if not isinstance(self.max_size_bytes, int) or self.max_size_bytes <= 0:
            errors.append(
                f"transform.cache.max_size_bytes must be a positive integer "
                f"(found: {type(self.max_size_bytes).__name__} = {self.max_size_bytes!r}, "
                f"expected: integer > 0 like 1073741824)"
            )

        return errors

    def __post_init__(self):
        """Validate cache configuration after initialization."""
        errors = []
        errors.extend(self._validate_cache_location())
        errors.extend(self._validate_max_size())

        if errors:
            raise TransformConfigError(errors)


@dataclass
class EngineConfig:
    """Engine-specific configuration."""

    name: str
    enabled: bool
    options: Dict[str, Any]

    def _validate_name(self) -> List[str]:
        """Validate engine name is a non-empty string."""
        errors = []

        if not isinstance(self.name, str) or not self.name:
            errors.append(
                f"engine name must be a non-empty string "
                f"(found: {type(self.name).__name__} = {self.name!r}, "
                f"expected: string like 'docling')"
            )

        return errors

    def _validate_enabled(self) -> List[str]:
        """Validate enabled is a boolean."""
        errors = []

        if not isinstance(self.enabled, bool):
            errors.append(
                f"engine '{self.name}' enabled must be a boolean "
                f"(found: {type(self.enabled).__name__} = {self.enabled!r}, "
                f"expected: true or false)"
            )

        return errors

    def _validate_options(self) -> List[str]:
        """Validate options is a dictionary."""
        errors = []

        if not isinstance(self.options, dict):
            errors.append(
                f"engine '{self.name}' options must be a dict "
                f"(found: {type(self.options).__name__} = {self.options!r}, "
                f"expected: dict)"
            )

        return errors

    def __post_init__(self):
        """Validate engine configuration after initialization."""
        errors = []
        errors.extend(self._validate_name())
        errors.extend(self._validate_enabled())
        errors.extend(self._validate_options())

        if errors:
            raise TransformConfigError(errors)


@dataclass
class TransformConfig:
    """Transform configuration loaded from config dict with validation."""

    cache: CacheConfig
    engines: Dict[str, EngineConfig]
    database: str
    default_engine: str = "docling"

    def _validate_cache(self) -> List[str]:
        """Validate cache configuration."""
        errors = []

        if not isinstance(self.cache, CacheConfig):
            errors.append(
                f"transform.cache must be a CacheConfig instance "
                f"(found: {type(self.cache).__name__}, "
                f"expected: CacheConfig)"
            )

        return errors

    def _validate_engines(self) -> List[str]:
        """Validate engines configuration."""
        errors = []

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
        errors = []
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
            raise TransformConfigError([
                "transform section is required in config "
                "(found: missing, expected: transform section with cache and engines)"
            ])

        database = transform_config.get("database", "wks_transform")

        # Extract cache config
        cache_config = transform_config.get("cache", {})
        cache_location = cache_config.get("location", ".wks/transform/cache")
        max_size_bytes = cache_config.get("max_size_bytes", 1073741824)  # 1GB default

        cache = CacheConfig(
            location=cache_location,
            max_size_bytes=max_size_bytes
        )

        # Extract engines config
        engines_config = transform_config.get("engines", {})
        engines = {}

        for engine_name, engine_dict in engines_config.items():
            if not isinstance(engine_dict, dict):
                raise TransformConfigError([
                    f"transform.engines['{engine_name}'] must be a dict "
                    f"(found: {type(engine_dict).__name__}, "
                    f"expected: dict with 'enabled' and optional options)"
                ])

            enabled = engine_dict.get("enabled", False)
            options = dict(engine_dict)
            options.pop("enabled", None)  # Remove 'enabled' from options

            engines[engine_name] = EngineConfig(
                name=engine_name,
                enabled=enabled,
                options=options
            )

        default_engine = transform_config.get("default_engine", "docling")

        return cls(cache=cache, engines=engines, database=database, default_engine=default_engine)
