"""Monitor module - Filesystem monitoring configuration and operations.

This module provides all monitor-related functionality:
- MonitorConfig: Configuration dataclass with validation
- MonitorController: Business logic for monitor operations
- MonitorStatus: Status reporting
- MonitorValidator: Validation helpers
- MonitorOperations: Add/remove operations

All imports organized for easy access.
"""

from .config import MonitorConfig, ValidationError
from .controller import MonitorController
from .operations import MonitorOperations
from .status import (
    ConfigValidationResult,
    ListOperationResult,
    ManagedDirectoriesResult,
    ManagedDirectoryInfo,
    MonitorStatus,
)
from .validator import MonitorValidator

__all__ = [
    # Config
    "MonitorConfig",
    "ValidationError",
    # Controller
    "MonitorController",
    # Operations
    "MonitorOperations",
    # Status
    "MonitorStatus",
    "ConfigValidationResult",
    "ListOperationResult",
    "ManagedDirectoriesResult",
    "ManagedDirectoryInfo",
    # Validator
    "MonitorValidator",
]
