"""Status and result dataclasses for monitor operations."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ListOperationResult:
    """Result of adding/removing items from a monitor list."""

    success: bool
    message: str
    value_stored: Optional[str] = None
    value_removed: Optional[str] = None
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
                f"ListOperationResult: success cannot be True when not_found is True (found: success={self.success}, not_found={self.not_found}, expected: success=False when not_found=True)"
            )
        if self.success and self.already_exists:
            raise ValueError(
                f"ListOperationResult: success cannot be True when already_exists is True (found: success={self.success}, already_exists={self.already_exists}, expected: success=False when already_exists=True)"
            )
        if self.success and self.validation_failed:
            raise ValueError(
                f"ListOperationResult: success cannot be True when validation_failed is True (found: success={self.success}, validation_failed={self.validation_failed}, expected: success=False when validation_failed=True)"
            )


@dataclass
class ManagedDirectoryInfo:
    """Information about a managed directory."""

    priority: int
    valid: bool
    error: Optional[str] = None

    def __post_init__(self):
        """Validate after initialization."""
        if self.priority < 0:
            raise ValueError(
                f"ManagedDirectoryInfo.priority must be non-negative (found: {self.priority}, expected: integer >= 0)"
            )


@dataclass
class ManagedDirectoriesResult:
    """Result of get_managed_directories()."""

    managed_directories: Dict[str, int]
    count: int
    validation: Dict[str, ManagedDirectoryInfo]


@dataclass
class ConfigValidationResult:
    """Result of validate_config()."""

    issues: List[str] = field(default_factory=list)
    redundancies: List[str] = field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)
    include_dirnames: List[str] = field(default_factory=list)
    exclude_dirnames: List[str] = field(default_factory=list)
    include_globs: List[str] = field(default_factory=list)
    exclude_globs: List[str] = field(default_factory=list)
    include_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class MonitorStatus:
    """Monitor status data structure."""

    tracked_files: int
    issues: List[str] = field(default_factory=list)
    redundancies: List[str] = field(default_factory=list)
    managed_directories: Dict[str, ManagedDirectoryInfo] = field(default_factory=dict)
    include_paths: List[str] = field(default_factory=list)
    exclude_paths: List[str] = field(default_factory=list)
    include_dirnames: List[str] = field(default_factory=list)
    exclude_dirnames: List[str] = field(default_factory=list)
    include_globs: List[str] = field(default_factory=list)
    exclude_globs: List[str] = field(default_factory=list)
    include_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_dirname_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    include_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    exclude_glob_validation: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        """Validate after initialization."""
        if self.tracked_files < 0:
            raise ValueError(
                f"MonitorStatus.tracked_files must be non-negative (found: {self.tracked_files}, expected: integer >= 0)"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization using dataclasses.asdict."""
        return asdict(self)
