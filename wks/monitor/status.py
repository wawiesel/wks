"""Status and result dataclasses for monitor operations."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ListOperationResult:
    """Result of adding/removing items from a monitor list."""

    success: bool
    message: str
    value_stored: str | None = None
    value_removed: str | None = None
    not_found: bool = False
    already_exists: bool = False
    validation_failed: bool = False

    def __post_init__(self):
        """Validate after initialization."""
        if not self.message:
            raise ValueError(
                f"ListOperationResult.message cannot be empty (found: {self.message!r}, expected: non-empty string)"
            )
        if self.success and self.not_found:
            raise ValueError(
                f"ListOperationResult: success cannot be True when not_found is True "
                f"(found: success={self.success}, not_found={self.not_found}, "
                "expected: success=False when not_found=True)"
            )
        if self.success and self.already_exists:
            raise ValueError(
                f"ListOperationResult: success cannot be True when already_exists is True "
                f"(found: success={self.success}, already_exists={self.already_exists}, "
                "expected: success=False when already_exists=True)"
            )
        if self.success and self.validation_failed:
            raise ValueError(
                f"ListOperationResult: success cannot be True when validation_failed is True "
                f"(found: success={self.success}, validation_failed={self.validation_failed}, "
                "expected: success=False when validation_failed=True)"
            )


@dataclass
class ManagedDirectoryInfo:
    """Information about a managed directory."""

    priority: int
    valid: bool
    error: str | None = None

    def __post_init__(self):
        """Validate after initialization."""
        if self.priority < 0:
            raise ValueError(
                f"ManagedDirectoryInfo.priority must be non-negative (found: {self.priority}, expected: integer >= 0)"
            )


@dataclass
class ManagedDirectoriesResult:
    """Result of get_managed_directories()."""

    managed_directories: dict[str, int]
    count: int
    validation: dict[str, ManagedDirectoryInfo]


@dataclass
class ConfigValidationResult:
    """Result of validate_config()."""

    issues: list[str] = field(default_factory=list)
    redundancies: list[str] = field(default_factory=list)
    managed_directories: dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    include_dirnames: list[str] = field(default_factory=list)
    exclude_dirnames: list[str] = field(default_factory=list)
    include_globs: list[str] = field(default_factory=list)
    exclude_globs: list[str] = field(default_factory=list)
    include_dirname_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class MonitorStatus:
    """Monitor status data structure."""

    tracked_files: int
    issues: list[str] = field(default_factory=list)
    redundancies: list[str] = field(default_factory=list)
    managed_directories: dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: list[str] = field(default_factory=list)
    exclude_paths: list[str] = field(default_factory=list)
    include_dirnames: list[str] = field(default_factory=list)
    exclude_dirnames: list[str] = field(default_factory=list)
    include_globs: list[str] = field(default_factory=list)
    exclude_globs: list[str] = field(default_factory=list)
    include_dirname_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: dict[str, dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate after initialization."""
        if self.tracked_files < 0:
            raise ValueError(
                f"MonitorStatus.tracked_files must be non-negative "
                f"(found: {self.tracked_files}, expected: integer >= 0)"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization using dataclasses.asdict."""
        return asdict(self)
