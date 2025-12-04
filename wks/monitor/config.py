"""Monitor configuration dataclass with validation."""

from dataclasses import dataclass, field, fields
from typing import Any, Dict, List


class ValidationError(Exception):
    """Exception that collects multiple validation errors."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Validation failed with multiple errors:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


@dataclass
class MonitorConfig:
    """Monitor configuration loaded from config dict with validation."""

    include_paths: List[str]
    exclude_paths: List[str]
    include_dirnames: List[str]
    exclude_dirnames: List[str]
    include_globs: List[str]
    exclude_globs: List[str]
    database: str
    managed_directories: Dict[str, int]
    touch_weight: float = 0.1
    priority: Dict[str, Any] = field(default_factory=dict)
    max_documents: int = 1000000
    prune_interval_secs: float = 300.0

    def _validate_list_fields(self) -> List[str]:
        """Validate that all list fields are actually lists."""
        errors: List[str] = []

        if not isinstance(self.include_paths, list):
            errors.append(
                f"monitor.include_paths must be a list (found: {type(self.include_paths).__name__} = {self.include_paths!r}, expected: list)"
            )

        if not isinstance(self.exclude_paths, list):
            errors.append(
                f"monitor.exclude_paths must be a list (found: {type(self.exclude_paths).__name__} = {self.exclude_paths!r}, expected: list)"
            )

        if not isinstance(self.include_dirnames, list):
            errors.append(
                f"monitor.include_dirnames must be a list (found: {type(self.include_dirnames).__name__} = {self.include_dirnames!r}, expected: list)"
            )

        if not isinstance(self.exclude_dirnames, list):
            errors.append(
                f"monitor.exclude_dirnames must be a list (found: {type(self.exclude_dirnames).__name__} = {self.exclude_dirnames!r}, expected: list)"
            )

        if not isinstance(self.include_globs, list):
            errors.append(
                f"monitor.include_globs must be a list (found: {type(self.include_globs).__name__} = {self.include_globs!r}, expected: list)"
            )

        if not isinstance(self.exclude_globs, list):
            errors.append(
                f"monitor.exclude_globs must be a list (found: {type(self.exclude_globs).__name__} = {self.exclude_globs!r}, expected: list)"
            )

        if not isinstance(self.managed_directories, dict):
            errors.append(
                f"monitor.managed_directories must be a dict (found: {type(self.managed_directories).__name__} = {self.managed_directories!r}, expected: dict)"
            )

        return errors

    def _validate_database_format(self) -> List[str]:
        """Validate database string is in 'database.collection' format."""
        errors: List[str] = []

        if not isinstance(self.database, str) or "." not in self.database:
            errors.append(
                f"monitor.database must be in format 'database.collection' (found: {self.database!r}, expected: format like 'wks.monitor')"
            )
        elif isinstance(self.database, str):
            parts = self.database.split(".", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                errors.append(
                    f"monitor.database must be in format 'database.collection' (found: {self.database!r}, expected: format like 'wks.monitor' with both parts non-empty)"
                )

        return errors

    def _validate_numeric_fields(self) -> List[str]:
        """Validate numeric fields are correct types and in valid ranges."""
        errors: List[str] = []

        if not isinstance(self.touch_weight, (int, float)) or self.touch_weight < 0.001 or self.touch_weight > 1.0:
            errors.append(
                f"monitor.touch_weight must be a number between 0.001 and 1 (found: {type(self.touch_weight).__name__} = {self.touch_weight!r}, expected: float between 0.001 and 1.0)"
            )

        if not isinstance(self.max_documents, int) or self.max_documents < 0:
            errors.append(
                f"monitor.max_documents must be a non-negative integer (found: {type(self.max_documents).__name__} = {self.max_documents!r}, expected: integer >= 0)"
            )

        if not isinstance(self.prune_interval_secs, (int, float)) or self.prune_interval_secs <= 0:
            errors.append(
                f"monitor.prune_interval_secs must be a positive number (found: {type(self.prune_interval_secs).__name__} = {self.prune_interval_secs!r}, expected: float > 0)"
            )

        return errors

    def __post_init__(self):
        """Validate monitor configuration after initialization.

        Collects all validation errors and raises a single ValidationError
        with all errors, so the user can see everything that needs fixing.
        """
        errors: List[str] = []
        errors.extend(self._validate_list_fields())
        errors.extend(self._validate_database_format())
        errors.extend(self._validate_numeric_fields())

        if errors:
            raise ValidationError(errors)

    @classmethod
    def from_config_dict(cls, config: dict) -> "MonitorConfig":
        """Load monitor config from config dict.

        Raises:
            KeyError: If monitor section is missing
            ValidationError: If field values are invalid (contains all validation errors)
        """
        monitor_config = config.get("monitor")
        if not monitor_config:
            raise KeyError(
                "monitor section is required in config (found: missing, expected: monitor section with include_paths, exclude_paths, etc.)"
            )

        monitor_config = dict(monitor_config)

        allowed = {f.name for f in fields(cls)}
        unsupported = [key for key in monitor_config.keys() if key not in allowed]
        if unsupported:
            errors: List[str] = [
                (
                    "Unsupported monitor config key '"
                    + key
                    + "' (remove it; supported keys: "
                    + ", ".join(sorted(allowed))
                    + ")"
                )
                for key in unsupported
            ]
            raise ValidationError(errors)

        return cls(**{k: monitor_config[k] for k in allowed if k in monitor_config})
