"""Cache configuration."""

from dataclasses import dataclass
from pathlib import Path

from ._TransformConfigError import _TransformConfigError


@dataclass
class _CacheConfig:
    """Cache configuration for transformed files."""

    base_dir: str
    max_size_bytes: int

    def _validate_base_dir(self) -> list[str]:
        """Validate base_dir is a non-empty string or Path."""
        errors: list[str] = []

        if not isinstance(self.base_dir, (str, Path)) or not str(self.base_dir):
            errors.append(
                f"transform.cache.base_dir must be a non-empty string or Path "
                f"(found: {type(self.base_dir).__name__} = {self.base_dir!r}, "
                f"expected: path string like '~/_transform')"
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
        errors.extend(self._validate_base_dir())
        errors.extend(self._validate_max_size())

        if errors:
            raise _TransformConfigError(errors)
