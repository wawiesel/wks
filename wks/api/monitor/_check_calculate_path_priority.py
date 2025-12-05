"""Calculate priority info for monitor check."""

from pathlib import Path
from typing import Tuple, List, Dict

from ._calculate_priority import _calculate_priority


def _check_calculate_path_priority(test_path: Path, monitor_cfg, decisions: list[dict[str, str]]) -> tuple[float | None, list[dict[str, str]]]:
    """Calculate priority for a path using configured weights."""
    try:
        priority = _calculate_priority(test_path, monitor_cfg.managed_directories, monitor_cfg.priority)
        decisions.append({"symbol": "✓", "message": f"Priority calculated: {priority}"})
        return float(priority), decisions
    except Exception as exc:  # pragma: no cover - defensive
        decisions.append({"symbol": "⚠", "message": f"Could not calculate priority: {exc}"})
        return None, decisions
