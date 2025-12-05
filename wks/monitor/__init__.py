"""Monitor module - Filesystem monitoring functionality.

This module provides monitor-related functionality:
- MonitorConfig: Configuration (from wks.api.monitor)
- start_monitoring: Filesystem monitoring
- WKSFileMonitor: Event handler
"""

# Import filesystem monitoring functionality from filesystem_monitor module
from ..filesystem_monitor import WKSFileMonitor, start_monitoring
from ..api.monitor.MonitorConfig import MonitorConfig
from pydantic import ValidationError

__all__ = [
    "MonitorConfig",
    "ValidationError",
    "WKSFileMonitor",
    "start_monitoring",
]
