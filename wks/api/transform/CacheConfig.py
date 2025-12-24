"""Cache configuration."""

from dataclasses import dataclass
from pathlib import Path

from .TransformConfigError import TransformConfigError


@dataclass
class CacheConfig:
    """Cache configuration for transformed files."""

    location: str
    max_size_bytes: int

    def _validate_cache_location(self) -> list[str]:
        """Validate cache location is a non-empty string or Path."""
        errors: list[str] = []

        if not isinstance(self.location, (str, Path)) or not str(self.location):
            errors.append(
                f"transform.cache.location must be a non-empty string or Path "
                f"(found: {type(self.location).__name__} = {self.location!r}, "
                f"expected: path string like '.wks/transform/cache')"
            )

        return errors

    def _validate_max_size(self) -> list[str]:
        """Validate max_size_bytes is a positive integer."""
        errors: list[str] = []

        if not isinstance(self.max_size_bytes, int) or self.max_size_bytes <= 0:
            errors.append(
                f"transform.cache.max_size_bytes must be a positive integer "
                f"(found: {type(self.max_size_bytes).__name__} = {self.max_size_bytes!r}, "
                f"expected: integer > 0 like 1073741824)"
            )

        return errors

    def __post_init__(self):
        """Validate cache configuration after initialization."""
        errors: list[str] = []
        errors.extend(self._validate_cache_location())
        errors.extend(self._validate_max_size())

        if errors:
            raise TransformConfigError(errors)
