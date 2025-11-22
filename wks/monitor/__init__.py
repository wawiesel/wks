"""Monitor module - Filesystem monitoring configuration and operations.

This module provides all monitor-related functionality:
- MonitorConfig: Configuration dataclass with validation
- MonitorController: Business logic for monitor operations
- MonitorStatus: Status reporting
- MonitorValidator: Validation helpers
- MonitorOperations: Add/remove operations
- start_monitoring: Filesystem monitoring (re-exported from parent monitor.py)
- WKSFileMonitor: Event handler (re-exported from parent monitor.py)

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

# Import filesystem monitoring functionality from filesystem_monitor module
from ..filesystem_monitor import start_monitoring, WKSFileMonitor

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
    # Filesystem monitoring (from parent monitor.py)
    "start_monitoring",
    "WKSFileMonitor",
]
