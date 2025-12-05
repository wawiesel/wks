"""Monitor priority-show API function.

This function lists all managed directories.
Matches CLI: wksc monitor priority show, MCP: wksm_monitor_priority_show
"""

from pathlib import Path

from ...config import WKSConfig
from ..base import StageResult
from ._ManagedDirectoriesResult import _PriorityDirectoriesResult
from ._ManagedDirectoryInfo import _ManagedDirectoryInfo
from ._rules import MonitorRules


def cmd_priority_show() -> StageResult:
    """List all managed directories with their priorities."""
    config = WKSConfig.load()
    monitor_cfg = config.monitor
    rules = MonitorRules.from_config(monitor_cfg)

    validation: dict[str, _ManagedDirectoryInfo] = {}
    for path, priority in monitor_cfg.managed_directories.items():
        allowed, trace = rules.explain(Path(path).expanduser().resolve())
        validation[path] = _ManagedDirectoryInfo(
            priority=priority, valid=allowed, error=None if allowed else (trace[-1] if trace else "Excluded by rules")
        )

    result_obj = _PriorityDirectoriesResult(
        priority_directories=monitor_cfg.managed_directories,
        count=len(monitor_cfg.managed_directories),
        validation=validation,
    )
    result = result_obj.model_dump()

    return StageResult(
        announce="Listing managed directories...",
        result="Managed directories retrieved",
        output=result,
    )
