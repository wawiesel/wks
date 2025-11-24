"""Helper functions for monitor status display - reduces complexity."""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from ...monitor import MonitorValidator


# Color constants for consistent styling
COLOR_FILES_KEY = "bold purple"
COLOR_FILES_VALUE = "purple"
COLOR_LAST_TOUCH_KEY = "bold green"
COLOR_LAST_TOUCH_VALUE = "green"
COLOR_HEADING = "bold cyan"
COLOR_PATH_BG = "on gray30"


@dataclass
class MonitorStatusDisplayData:
    """Collected data for monitor status display."""
    total_files: int
    managed_dirs_dict: Dict[str, Any]
    issues: List[str]
    redundancies: List[str]
    include_paths: Set[str]
    exclude_paths: Set[str]
    status_data: Any
    config: Dict[str, Any]


def build_files_and_touch_rows(total_files: int, last_touch: str) -> List[Tuple[str, str]]:
    """Build rows for files count and last touch time."""
    return [
        (f"[{COLOR_FILES_KEY}]files[/{COLOR_FILES_KEY}]", f"[{COLOR_FILES_VALUE}]{str(total_files)}[/{COLOR_FILES_VALUE}]"),
        (f"[{COLOR_LAST_TOUCH_KEY}]last touch[/{COLOR_LAST_TOUCH_KEY}]", f"[{COLOR_LAST_TOUCH_VALUE}]{last_touch}[/{COLOR_LAST_TOUCH_VALUE}]"),
        ("", ""),  # Empty row separator
    ]


def build_managed_dirs_rows(managed_dirs_dict: Dict[str, Any], red_paths: Set[str], yellow_paths: Set[str],
                            max_pip_count: int, max_num_width: int) -> List[Tuple[str, str]]:
    """Build rows for managed directories section."""
    rows = [(f"[{COLOR_HEADING}]managed_directories[/{COLOR_HEADING}]", str(len(managed_dirs_dict)))]

    for path, path_info in sorted(managed_dirs_dict.items(), key=lambda x: -x[1].priority):
        priority = path_info.priority
        is_valid = path_info.valid
        error_msg = path_info.error

        pip_count = 1 if priority <= 1 else int(math.log10(priority)) + 1
        pips = "▪" * pip_count
        status_symbol = MonitorValidator.status_symbol(error_msg, is_valid)
        priority_display = f"{pips.ljust(max_pip_count)} {str(priority).rjust(max_num_width)} {status_symbol}"
        rows.append((f"  [{COLOR_PATH_BG}]{path}[/{COLOR_PATH_BG}]", priority_display))

    rows.append(("", ""))
    return rows


def build_paths_rows(paths: Set[str], label: str, red_paths: Set[str], yellow_paths: Set[str]) -> List[Tuple[str, str]]:
    """Build rows for include/exclude paths sections."""
    rows = [(f"[{COLOR_HEADING}]{label}[/{COLOR_HEADING}]", str(len(paths)))]

    for path in sorted(paths):
        error_msg = None if path not in (red_paths | yellow_paths) else "issue"
        is_valid = path not in red_paths
        rows.append((f"  [{COLOR_PATH_BG}]{path}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    rows.append(("", ""))
    return rows


def build_dirnames_globs_rows(items: List[str], label: str, validation_dict: Dict) -> List[Tuple[str, str]]:
    """Build rows for dirnames or globs sections."""
    rows = [(f"[{COLOR_HEADING}]{label}[/{COLOR_HEADING}]", str(len(items)))]

    for item in items:
        validation_info = validation_dict.get(item, {})
        error_msg = validation_info.get("error")
        is_valid = validation_info.get("valid", True)
        rows.append((f"  [{COLOR_PATH_BG}]{item}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    rows.append(("", ""))
    return rows
