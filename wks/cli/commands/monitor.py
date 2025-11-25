"""Monitor commands - filesystem monitoring status and configuration (Monitor Layer)."""

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ...config import get_config_path, load_config
from ...constants import MAX_DISPLAY_WIDTH
from ...monitor import MonitorController, MonitorValidator

SUPPORTED_MONITOR_LISTS = {
    "include_paths",
    "exclude_paths",
    "include_dirnames",
    "exclude_dirnames",
    "include_globs",
    "exclude_globs",
}
from ...utils import wks_home_path


# Helper functions for monitor status display
def path_matches_message(path: str, message: str) -> bool:
    """Check if path appears in message."""
    return f"'{path}'" in message or f" {path}" in message or message.endswith(path)


def extract_paths_from_messages(messages: List[str], all_paths: List[str]) -> Set[str]:
    """Extract paths that appear in messages."""
    matched = set()
    for message in messages:
        for path in all_paths:
            if path_matches_message(path, message):
                matched.add(path)
    return matched


def build_problematic_paths(issues: List[str], redundancies: List[str],
                            managed_dirs: Dict, include_paths: set, exclude_paths: set) -> Tuple[set, set]:
    """Build sets of problematic paths for coloring."""
    all_paths = list(managed_dirs.keys()) + list(include_paths) + list(exclude_paths)
    red_paths = extract_paths_from_messages(issues, all_paths)
    yellow_paths = extract_paths_from_messages(redundancies, all_paths)
    return red_paths, yellow_paths


def calculate_priority_alignment(managed_dirs_dict: Dict) -> Tuple[int, int]:
    """Calculate max pip count and number width for priority alignment."""
    max_pip_count = 0
    max_num_width = 0
    for path_info in managed_dirs_dict.values():
        priority = path_info.priority
        pip_count = 1 if priority <= 1 else int(math.log10(priority)) + 1
        max_pip_count = max(max_pip_count, pip_count)
        max_num_width = max(max_num_width, len(str(priority)))
    return max_pip_count, max_num_width


def style_setting_column(text: str) -> str:
    """Style setting column text (background is applied at column level)."""
    # Background is now applied at the column level, so just return the text
    return text


def build_managed_dirs_rows(managed_dirs_dict: Dict, max_pip_count: int, max_num_width: int) -> List[Dict]:
    """Build table rows for managed directories."""
    rows = []
    for path, path_info in sorted(managed_dirs_dict.items(), key=lambda x: -x[1].priority):
        priority = path_info.priority
        is_valid = path_info.valid
        error_msg = path_info.error

        pip_count = 1 if priority <= 1 else int(math.log10(priority)) + 1
        pips = "▪" * pip_count
        status_symbol = MonitorValidator.status_symbol(error_msg, is_valid)
        priority_display = f"{pips.ljust(max_pip_count)} {str(priority).rjust(max_num_width)} {status_symbol}"

        styled_path = style_setting_column(f"  {path}")
        rows.append({"Setting": styled_path, "Value": priority_display})
    return rows


def build_path_list_rows(paths: set, red_paths: set, yellow_paths: set, label: str) -> List[Dict]:
    """Build table rows for include/exclude paths."""
    styled_label = style_setting_column(f"[bold cyan]{label}[/bold cyan]")
    rows = [{"Setting": styled_label, "Value": str(len(paths))}]
    for path in sorted(paths):
        error_msg = None if path not in (red_paths | yellow_paths) else "issue"
        is_valid = path not in red_paths
        styled_path = style_setting_column(f"  {path}")
        rows.append({"Setting": styled_path, "Value": MonitorValidator.status_symbol(error_msg, is_valid)})
    return rows



def load_monitor_config() -> Dict[str, Any]:
    """Load monitor configuration."""
    return load_config()


def extract_monitor_status_data(status_data: Any) -> Tuple[int, List[str], List[str], Dict[str, int], Set[str], Set[str]]:
    """Extract data from monitor status.

    Returns:
        Tuple of (total_files, issues, redundancies, managed_dirs_dict, include_paths, exclude_paths)
    """
    total_files = status_data.tracked_files
    issues = status_data.issues
    redundancies = status_data.redundancies
    managed_dirs_dict = status_data.managed_directories
    include_paths = set(status_data.include_paths)
    exclude_paths = set(status_data.exclude_paths)
    return total_files, issues, redundancies, managed_dirs_dict, include_paths, exclude_paths


def get_last_touch_time(config: Dict[str, Any]) -> Optional[str]:
    """Get the most recent timestamp from the monitor database."""
    try:
        from ...config import mongo_settings
        from pymongo import MongoClient
        from ...monitor import MonitorConfig

        monitor_cfg = MonitorConfig.from_config_dict(config)
        mongo_config = mongo_settings(config)

        client = MongoClient(mongo_config["uri"], serverSelectionTimeoutMS=5000)
        client.server_info()
        db_name, coll_name = monitor_cfg.database.split(".", 1)
        db = client[db_name]
        collection = db[coll_name]

        # Find the document with the most recent timestamp
        latest_doc = collection.find_one(
            {"timestamp": {"$exists": True}},
            sort=[("timestamp", -1)]
        )
        client.close()

        if latest_doc and latest_doc.get("timestamp"):
            # Parse ISO timestamp and format it nicely
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(latest_doc["timestamp"])
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                return latest_doc["timestamp"]
        return None
    except Exception:
        return None


def build_monitor_status_table_data(
    total_files: int,
    managed_dirs_dict: Dict[str, Any],  # Dict[str, ManagedDirectoryInfo]
    issues: List[str],
    redundancies: List[str],
    include_paths: Set[str],
    exclude_paths: Set[str],
    status_data: Any,
    config: Dict[str, Any]
) -> List[Tuple[str, str]]:
    """Build simple key/value pairs for monitor status display.

    Returns:
        List of (key, value) tuples for monitor status data, including files and last touch
    """
    from .monitor_status_helpers import (
        MonitorStatusDisplayData,
        build_files_and_touch_rows,
        build_managed_dirs_rows,
        build_paths_rows,
        build_dirnames_globs_rows,
    )

    # Get last touch time
    last_touch = get_last_touch_time(config) or "Never"

    # Calculate problematic paths and alignment once
    red_paths, yellow_paths = build_problematic_paths(issues, redundancies, managed_dirs_dict, include_paths, exclude_paths)
    max_pip_count, max_num_width = calculate_priority_alignment(managed_dirs_dict)
    max_pip_count = max(max_pip_count, 1)
    max_num_width = max(max_num_width, 1)

    # Build all sections
    rows = []
    rows.extend(build_files_and_touch_rows(total_files, last_touch))
    rows.extend(build_managed_dirs_rows(managed_dirs_dict, red_paths, yellow_paths, max_pip_count, max_num_width))
    rows.extend(build_paths_rows(include_paths, "include_paths", red_paths, yellow_paths))
    rows.extend(build_paths_rows(exclude_paths, "exclude_paths", red_paths, yellow_paths))
    rows.extend(build_dirnames_globs_rows(status_data.include_dirnames, "include_dirnames", status_data.include_dirname_validation))
    rows.extend(build_dirnames_globs_rows(status_data.exclude_dirnames, "exclude_dirnames", status_data.exclude_dirname_validation))
    rows.extend(build_dirnames_globs_rows(status_data.include_globs, "include_globs", status_data.include_glob_validation))
    rows.extend(build_dirnames_globs_rows(status_data.exclude_globs, "exclude_globs", status_data.exclude_glob_validation))

    return rows


def display_monitor_status_table(
    display: Any,
    monitor_status_rows: List[Tuple[str, str]]
) -> None:
    """Display monitor status rows using the shared two-column table helper."""
    from ..helpers import display_status_table

    display_status_table(display, monitor_status_rows, title="Monitor Status")


def display_monitor_status_issues_panel(display: Any, issues: List[str], redundancies: List[str]) -> None:
    """Display issues and redundancies in a panel on STDOUT."""
    content_lines = []

    if issues:
        content_lines.append(f"[bold red]Inconsistencies ({len(issues)}):[/bold red]")
        for issue in issues:
            content_lines.append(f"  • {issue}")
        if redundancies:
            content_lines.append("")  # Blank line between sections

    if redundancies:
        content_lines.append(f"[bold yellow]Redundancies ({len(redundancies)}):[/bold yellow]")
        for redund in redundancies:
            content_lines.append(f"  • {redund}")

    if content_lines:
        content = "\n".join(content_lines)
        title = "Configuration Issues" if issues else "Configuration Warnings"
        border_style = "red" if issues else "yellow"
        display.panel(content, title=title, border_style=border_style, width=MAX_DISPLAY_WIDTH)


# Monitor command implementations
def monitor_status_cmd(args: argparse.Namespace) -> int:
    """Show monitoring statistics.

    Follows the 4-step process:
    1. Say what you're doing on STDERR
    2. Start progress bar on STDERR
    3. Say what you did and if there were problems on STDERR
    4. Display output on STDOUT
    """
    # Live mode requires CLI display
    live = getattr(args, "live", False)
    if live:
        args.display = "cli"
        from ...display.context import get_display
        args.display_obj = get_display("cli")
        return _monitor_status_live(args)

    # Step 1: Say what you're doing on STDERR (include config file path)
    config_file = get_config_path()
    print(f"Loading monitor configuration from {config_file}...", file=sys.stderr)

    # Step 2: Start progress bar on STDERR
    display = args.display_obj
    progress_handle = display.progress_start(total=3, description="Loading monitor status")

    try:
        # Load config (no informational output to STDOUT)
        cfg = load_monitor_config()
        display.progress_update(progress_handle, advance=1, description="Gathering monitor status")

        status_data = MonitorController.get_status(cfg)
        display.progress_update(progress_handle, advance=1, description="Building status display")

        total_files, issues, redundancies, managed_dirs_dict, include_paths, exclude_paths = extract_monitor_status_data(status_data)

        monitor_status_rows = build_monitor_status_table_data(
            total_files, managed_dirs_dict, issues, redundancies, include_paths, exclude_paths, status_data, cfg
        )

        display.progress_update(progress_handle, advance=1, description="Complete")
        display.progress_finish(progress_handle)

        # Step 3: Say what you did and if there were problems on STDERR
        problems = len(issues) + len(redundancies)
        if problems > 0:
            print(f"Monitor status loaded with {problems} issue(s) found", file=sys.stderr)
        else:
            print("Monitor status loaded successfully", file=sys.stderr)

        # Step 4: Display output on STDOUT (table and issues panel)
        display_monitor_status_table(display, monitor_status_rows)

        # Display issues/redundancies panel after the table
        if issues or redundancies:
            display_monitor_status_issues_panel(display, issues, redundancies)

    except Exception as e:
        display.progress_finish(progress_handle)
        import traceback
        print(f"Error loading monitor status: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    return 0


def _monitor_status_live(args: argparse.Namespace) -> int:
    """Render live-updating monitor status display."""
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from ...constants import MAX_DISPLAY_WIDTH
    from ..helpers import display_status_table

    console = Console(width=MAX_DISPLAY_WIDTH)

    def _render_status() -> Panel:
        """Render current status as a Rich panel with unified table."""
        cfg = load_monitor_config()
        status_data = MonitorController.get_status(cfg)
        total_files, issues, redundancies, managed_dirs_dict, include_paths, exclude_paths = extract_monitor_status_data(status_data)

        monitor_status_rows = build_monitor_status_table_data(
            total_files, managed_dirs_dict, issues, redundancies, include_paths, exclude_paths, status_data, cfg
        )

        # Create a mock display object for the unified function
        class MockDisplay:
            def __init__(self, console):
                self.console = console

        mock_display = MockDisplay(console)

        # Build the panel manually since we need to return it
        from rich.table import Table
        from rich.columns import Columns

        key_width = 22
        value_width = 10
        row_tables = []
        for key, value in monitor_status_rows:
            row_table = Table(show_header=False, box=None, padding=(0, 1))
            row_table.add_column("Key", justify="left", width=key_width)
            row_table.add_column("Value", justify="right", width=value_width)
            row_table.add_row(key, value)
            row_tables.append(row_table)

        columns = Columns(row_tables, equal=True, column_first=True)
        return Panel.fit(columns, title="Monitor Status (Live)", border_style="cyan", width=MAX_DISPLAY_WIDTH)

    try:
        with Live(_render_status(), refresh_per_second=0.5, screen=False, console=console) as live:
            while True:
                time.sleep(2.0)
                try:
                    live.update(_render_status())
                except Exception as update_exc:
                    console.print(f"[yellow]Warning: {update_exc}[/yellow]", end="")
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped monitoring.[/dim]")
        return 0
    except Exception as exc:
        console.print(f"[red]Error in live mode: {exc}[/red]")
        return 2


# Validation helpers
def check_path_conflicts(include_paths: Set[str], exclude_paths: Set[str]) -> List[str]:
    """Check for paths in both include and exclude."""
    issues = []
    conflicts = include_paths & exclude_paths
    for path in conflicts:
        issues.append(f"Path in both include and exclude: {path}")
    return issues


def check_duplicate_managed_dirs(managed_dirs: Set[str]) -> List[str]:
    """Check for duplicate managed directories with same resolved path."""
    warnings = []
    managed_list = list(managed_dirs)
    for i, dir1 in enumerate(managed_list):
        p1 = Path(dir1).expanduser().resolve()
        for dir2 in managed_list[i + 1:]:
            p2 = Path(dir2).expanduser().resolve()
            try:
                if p1 == p2:
                    warnings.append(f"Duplicate managed directories: {dir1} and {dir2} resolve to same path")
            except BaseException:
                pass
    return warnings


def display_validation_results(display: Any, issues: List[str], warnings: List[str]) -> int:
    """Display validation results and return exit code."""
    if not issues and not warnings:
        display.success("No configuration issues found")
        return 0

    if issues:
        display.error(f"Found {len(issues)} error(s):")
        for issue in issues:
            display.error(f"  • {issue}")

    if warnings:
        display.warning(f"Found {len(warnings)} warning(s):")
        for warning in warnings:
            display.warning(f"  • {warning}")

    return 1 if issues else 0


def monitor_validate_cmd(args: argparse.Namespace) -> int:
    """Check for configuration inconsistencies."""
    display = args.display_obj
    cfg = load_config()

    # Use MonitorController for validation
    result = MonitorController.validate_config(cfg)

    # Display results
    if not result.issues and not result.redundancies:
        display.success("✓ No configuration issues found")
        return 0

    if result.issues:
        display.error(f"Found {len(result.issues)} issue(s):")
        for issue in result.issues:
            display.info(f"  • {issue}")

    if result.redundancies:
        display.warning(f"Found {len(result.redundancies)} redundanc(y/ies):")
        for redundancy in result.redundancies:
            display.info(f"  • {redundancy}")

    return 1 if result.issues else 0


def monitor_check_cmd(args: argparse.Namespace) -> int:
    """Check if a path would be monitored."""
    display = args.display_obj
    cfg = load_config()

    # Use MonitorController to check the path
    result = MonitorController.check_path(cfg, args.path)

    # Display results
    if result["is_monitored"]:
        display.success(f"Path WOULD be monitored: {result['path']}")
        if result.get("priority"):
            display.info(f"Priority: {result['priority']}")
    else:
        display.error(f"Path would NOT be monitored: {result['path']}")
        if result.get("reason"):
            display.error(f"Reason: {result['reason']}")

    # Show decision chain
    display.info("\nDecision chain:")
    for decision in result.get("decisions", []):
        symbol = decision.get("symbol", "ℹ")
        message = decision.get("message", "")
        if symbol == "✓":
            display.success(f"  {message}")
        elif symbol == "✗":
            display.error(f"  {message}")
        elif symbol == "⚠":
            display.warning(f"  {message}")
        else:
            display.info(f"  {message}")

    return 0 if result["is_monitored"] else 1


# List management helpers
def normalize_path_for_list(value: str, resolve_path: bool) -> Tuple[str, str]:
    """Normalize path for list operations.

    Returns:
        Tuple of (value_resolved, value_to_store)
    """
    if resolve_path:
        value_resolved = str(Path(value).expanduser().resolve())
        home_dir = str(Path.home())
        if value_resolved.startswith(home_dir):
            value_to_store = "~" + value_resolved[len(home_dir):]
        else:
            value_to_store = value_resolved
        return value_resolved, value_to_store
    normalized = value.strip()
    return normalized, normalized


def find_existing_entry_in_list(
    cfg: Dict[str, Any],
    list_name: str,
    value: str,
    value_resolved: str,
    resolve_path: bool
) -> Optional[str]:
    """Find existing entry in list by comparing resolved paths."""
    if resolve_path:
        for entry in cfg["monitor"][list_name]:
            entry_resolved = str(Path(entry).expanduser().resolve())
            if entry_resolved == value_resolved:
                return entry
        return None
    return value if value in cfg["monitor"][list_name] else None


def validate_before_add(
    cfg: Dict[str, Any],
    list_name: str,
    value: str,
    value_resolved: str,
    resolve_path: bool,
    display: Any
) -> int:
    """Validate before adding to list. Returns 0 if valid, 1 if invalid."""
    target_value = value if not resolve_path else value_resolved
    if list_name in ("include_dirnames", "exclude_dirnames"):
        is_valid, error_msg = MonitorValidator.validate_dirname_entry(target_value)
        if not is_valid:
            display.error(error_msg)
            return 1
        opposite = "exclude_dirnames" if list_name == "include_dirnames" else "include_dirnames"
        other_values = set(cfg["monitor"].get(opposite, []))
        if target_value in other_values:
            display.error(f"Directory name '{target_value}' already present in {opposite}")
            return 1
    elif list_name in ("include_globs", "exclude_globs"):
        is_valid, error_msg = MonitorValidator.validate_glob_pattern(target_value)
        if not is_valid:
            display.error(error_msg)
            return 1
    return 0


def perform_list_add(
    cfg: Dict[str, Any],
    list_name: str,
    value_to_store: str,
    existing_entry: Optional[str],
    display: Any
) -> int:
    """Perform add operation. Returns exit code."""
    if existing_entry:
        display.warning(f"Already in {list_name}: {existing_entry}")
        return 0
    cfg["monitor"][list_name].append(value_to_store)
    display.success(f"Added to {list_name}: {value_to_store}")
    return 0


def perform_list_remove(
    cfg: Dict[str, Any],
    list_name: str,
    value: str,
    existing_entry: Optional[str],
    display: Any
) -> int:
    """Perform remove operation. Returns exit code."""
    if not existing_entry:
        display.warning(f"Not in {list_name}: {value}")
        return 0
    cfg["monitor"][list_name].remove(existing_entry)
    display.success(f"Removed from {list_name}: {existing_entry}")
    return 0


def modify_monitor_list(display, list_name: str, value: str, operation: str, resolve_path: bool = True) -> int:
    """Modify a monitor config list (add/remove)."""
    if list_name not in SUPPORTED_MONITOR_LISTS:
        display.error(
            f"Unsupported monitor list '{list_name}'. Allowed lists: {', '.join(sorted(SUPPORTED_MONITOR_LISTS))}"
        )
        return 2
    config_path = get_config_path()

    if not config_path.exists():
        display.error(f"Config file not found: {config_path}")
        return 2

    # Read current config
    cfg = load_config(config_path)

    # Get monitor section
    if "monitor" not in cfg:
        cfg["monitor"] = {}

    if list_name not in cfg["monitor"]:
        cfg["monitor"][list_name] = []

    # Normalize path for comparison if needed
    value_resolved, value_to_store = normalize_path_for_list(value, resolve_path)
    existing_entry = find_existing_entry_in_list(cfg, list_name, value, value_resolved, resolve_path)

    # Perform operation
    if operation == "add":
        exit_code = validate_before_add(cfg, list_name, value, value_resolved, resolve_path, display)
        if exit_code != 0:
            return exit_code
        exit_code = perform_list_add(cfg, list_name, value_to_store, existing_entry, display)
        if exit_code != 0:
            return exit_code
    elif operation == "remove":
        exit_code = perform_list_remove(cfg, list_name, value, existing_entry, display)
        if exit_code != 0:
            return exit_code

    # Write back
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)

    display.info("Restart the monitor service for changes to take effect")
    return 0


def show_monitor_list(display, list_name: str, title: str) -> int:
    """Show contents of a monitor config list with validation status."""
    cfg = load_config()
    if list_name not in SUPPORTED_MONITOR_LISTS:
        display.error(
            f"Unsupported monitor list '{list_name}'. Allowed lists: {', '.join(sorted(SUPPORTED_MONITOR_LISTS))}"
        )
        return 2

    try:
        list_info = MonitorController.get_list(cfg, list_name)
    except (KeyError, ValueError) as exc:
        display.error(str(exc))
        return 2

    items = list_info.get("items", [])
    if not items:
        display.info(f"No {list_name} configured")
        return 0

    validation = list_info.get("validation", {})
    monitor_config = cfg.get("monitor", {})

    table_data = []
    for i, item in enumerate(items, 1):
        is_valid, error_msg = True, None
        if list_name in ("include_paths", "exclude_paths"):
            try:
                path_obj = Path(item).expanduser().resolve()
                if not path_obj.exists():
                    is_valid = list_name == "exclude_paths"
                    error_msg = "Path does not exist" + (" (ok for exclude list)" if is_valid else "")
                elif not path_obj.is_dir():
                    is_valid, error_msg = False, "Not a directory"
            except Exception as e:
                is_valid, error_msg = False, f"Invalid path: {e}"
        else:
            entry_validation = validation.get(item, {})
            is_valid = entry_validation.get("valid", True)
            error_msg = entry_validation.get("error")

        table_data.append({"#": str(i), "Value": item, "Status": MonitorValidator.status_symbol(error_msg, is_valid)})

    display.table(table_data, title=title)
    return 0


# Command handlers for list operations
def monitor_include_default(args: argparse.Namespace) -> int:
    """Default action for include_paths: show list."""
    if not args.include_paths_op:
        return show_monitor_list(args.display_obj, "include_paths", "Include Paths")
    return 0


def monitor_include_add(args: argparse.Namespace) -> int:
    """Add path(s) to include_paths."""
    for path in args.paths:
        result = modify_monitor_list(args.display_obj, "include_paths", path, "add", resolve_path=True)
        if result != 0:
            return result
    return 0


def monitor_include_remove(args: argparse.Namespace) -> int:
    """Remove path(s) from include_paths."""
    for path in args.paths:
        result = modify_monitor_list(args.display_obj, "include_paths", path, "remove", resolve_path=True)
        if result != 0:
            return result
    return 0


def monitor_exclude_default(args: argparse.Namespace) -> int:
    """Default action for exclude_paths: show list."""
    if not args.exclude_paths_op:
        return show_monitor_list(args.display_obj, "exclude_paths", "Exclude Paths")
    return 0


def monitor_exclude_add(args: argparse.Namespace) -> int:
    """Add path(s) to exclude_paths."""
    for path in args.paths:
        result = modify_monitor_list(args.display_obj, "exclude_paths", path, "add", resolve_path=True)
        if result != 0:
            return result
    return 0


def monitor_exclude_remove(args: argparse.Namespace) -> int:
    """Remove path(s) from exclude_paths."""
    for path in args.paths:
        result = modify_monitor_list(args.display_obj, "exclude_paths", path, "remove", resolve_path=True)
        if result != 0:
            return result
    return 0


def monitor_include_dirnames_default(args: argparse.Namespace) -> int:
    """Default action for include_dirnames: show list."""
    if not args.include_dirnames_op:
        return show_monitor_list(args.display_obj, "include_dirnames", "Included Directory Names")
    return 0


def monitor_include_dirnames_add(args: argparse.Namespace) -> int:
    """Add directory name(s) to include_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "include_dirnames", dirname, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_include_dirnames_remove(args: argparse.Namespace) -> int:
    """Remove directory name(s) from include_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "include_dirnames", dirname, "remove", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_exclude_dirnames_default(args: argparse.Namespace) -> int:
    """Default action for exclude_dirnames: show list."""
    if not args.exclude_dirnames_op:
        return show_monitor_list(args.display_obj, "exclude_dirnames", "Excluded Directory Names")
    return 0


def monitor_exclude_dirnames_add(args: argparse.Namespace) -> int:
    """Add directory name(s) to exclude_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "exclude_dirnames", dirname, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_exclude_dirnames_remove(args: argparse.Namespace) -> int:
    """Remove directory name(s) from exclude_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "exclude_dirnames", dirname, "remove", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_include_globs_default(args: argparse.Namespace) -> int:
    """Default action for include_globs: show list."""
    if not args.include_globs_op:
        return show_monitor_list(args.display_obj, "include_globs", "Included Glob Patterns")
    return 0


def monitor_include_globs_add(args: argparse.Namespace) -> int:
    """Add glob pattern(s) to include_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "include_globs", pattern, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_include_globs_remove(args: argparse.Namespace) -> int:
    """Remove glob pattern(s) from include_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "include_globs", pattern, "remove", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_exclude_globs_default(args: argparse.Namespace) -> int:
    """Default action for exclude_globs: show list."""
    if not args.exclude_globs_op:
        return show_monitor_list(args.display_obj, "exclude_globs", "Excluded Glob Patterns")
    return 0


def monitor_exclude_globs_add(args: argparse.Namespace) -> int:
    """Add glob pattern(s) to exclude_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "exclude_globs", pattern, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_exclude_globs_remove(args: argparse.Namespace) -> int:
    """Remove glob pattern(s) from exclude_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "exclude_globs", pattern, "remove", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_managed_default(args: argparse.Namespace) -> int:
    """Default action for managed: show list."""
    if not args.managed_op:
        cfg = load_config()
        monitor_config = cfg.get("monitor", {})
        managed_dirs = monitor_config.get("managed_directories", {})

        if not managed_dirs:
            args.display_obj.info("No managed_directories configured")
            return 0

        table_data = []
        for path, priority in sorted(managed_dirs.items(), key=lambda x: -x[1]):
            table_data.append({"Path": path, "Priority": str(priority)})

        args.display_obj.table(table_data, title="Managed Directories")
        return 0
    return 0


def monitor_managed_add(args: argparse.Namespace) -> int:
    """Add managed directory with priority."""
    config_path = get_config_path()

    if not config_path.exists():
        args.display_obj.error(f"Config file not found: {config_path}")
        return 2

    path = str(Path(args.path).expanduser().resolve())

    with open(config_path) as f:
        cfg = json.load(f)

    if "monitor" not in cfg:
        cfg["monitor"] = {}
    if "managed_directories" not in cfg["monitor"]:
        cfg["monitor"]["managed_directories"] = {}

    cfg["monitor"]["managed_directories"][path] = args.priority

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)

    args.display_obj.success(f"Added managed directory: {path} (priority {args.priority})")
    args.display_obj.info("Restart the monitor service for changes to take effect")
    return 0


def monitor_managed_remove(args: argparse.Namespace) -> int:
    """Remove managed directory."""
    config_path = get_config_path()

    if not config_path.exists():
        args.display_obj.error(f"Config file not found: {config_path}")
        return 2

    path = str(Path(args.path).expanduser().resolve())

    with open(config_path) as f:
        cfg = json.load(f)

    if "monitor" not in cfg or "managed_directories" not in cfg["monitor"]:
        args.display_obj.warning("No managed_directories configured")
        return 0

    if path not in cfg["monitor"]["managed_directories"]:
        args.display_obj.warning(f"Not a managed directory: {path}")
        return 0

    del cfg["monitor"]["managed_directories"][path]

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)

    args.display_obj.success(f"Removed managed directory: {path}")
    args.display_obj.info("Restart the monitor service for changes to take effect")
    return 0


def monitor_managed_priority(args: argparse.Namespace) -> int:
    """Set priority for managed directory."""
    config_path = get_config_path()

    if not config_path.exists():
        args.display_obj.error(f"Config file not found: {config_path}")
        return 2

    path = str(Path(args.path).expanduser().resolve())

    with open(config_path) as f:
        cfg = json.load(f)

    if "monitor" not in cfg or "managed_directories" not in cfg["monitor"]:
        args.display_obj.error("No managed_directories configured")
        return 2

    if path not in cfg["monitor"]["managed_directories"]:
        args.display_obj.error(f"Not a managed directory: {path}")
        return 2

    old_priority = cfg["monitor"]["managed_directories"][path]
    cfg["monitor"]["managed_directories"][path] = args.priority

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)

    args.display_obj.success(f"Updated priority: {path} ({old_priority} → {args.priority})")
    args.display_obj.info("Restart the monitor service for changes to take effect")
    return 0


def setup_monitor_parser(subparsers) -> None:
    """Setup monitor command parser."""
    mon = subparsers.add_parser("monitor", help="Filesystem monitoring status and configuration")
    monsub = mon.add_subparsers(dest="monitor_cmd", required=False)

    def _monitor_help(args, parser=mon):
        parser.print_help()
        return 2

    mon.set_defaults(func=_monitor_help)

    # monitor status
    monstatus = monsub.add_parser("status", help="Show monitoring statistics")
    monstatus.add_argument(
        "--live",
        action="store_true",
        help="Keep display updated automatically (refreshes every 2 seconds)"
    )
    monstatus.set_defaults(func=monitor_status_cmd)

    # monitor validate
    monvalidate = monsub.add_parser("validate", help="Check for configuration inconsistencies")
    monvalidate.set_defaults(func=monitor_validate_cmd)

    # monitor check
    moncheck = monsub.add_parser("check", help="Check if a path would be monitored")
    moncheck.add_argument("path", help="Path to check")
    moncheck.set_defaults(func=monitor_check_cmd)

    # monitor include_paths
    mon_include = monsub.add_parser("include_paths", help="Manage include_paths")
    mon_include_sub = mon_include.add_subparsers(dest="include_paths_op", required=False)
    mon_include.set_defaults(func=monitor_include_default)
    mon_include_add = mon_include_sub.add_parser("add", help="Add path(s) to include_paths")
    mon_include_add.add_argument("paths", nargs='+', help="Path(s) to monitor")
    mon_include_add.set_defaults(func=monitor_include_add)
    mon_include_remove = mon_include_sub.add_parser("remove", help="Remove path(s) from include_paths")
    mon_include_remove.add_argument("paths", nargs='+', help="Path(s) to remove")
    mon_include_remove.set_defaults(func=monitor_include_remove)

    # monitor exclude_paths
    mon_exclude = monsub.add_parser("exclude_paths", help="Manage exclude_paths")
    mon_exclude_sub = mon_exclude.add_subparsers(dest="exclude_paths_op", required=False)
    mon_exclude.set_defaults(func=monitor_exclude_default)
    mon_exclude_add = mon_exclude_sub.add_parser("add", help="Add path(s) to exclude_paths")
    mon_exclude_add.add_argument("paths", nargs='+', help="Path(s) to exclude")
    mon_exclude_add.set_defaults(func=monitor_exclude_add)
    mon_exclude_remove = mon_exclude_sub.add_parser("remove", help="Remove path(s) from exclude_paths")
    mon_exclude_remove.add_argument("paths", nargs='+', help="Path(s) to remove")
    mon_exclude_remove.set_defaults(func=monitor_exclude_remove)

    # monitor include_dirnames
    mon_inc_dir = monsub.add_parser("include_dirnames", help="Manage include_dirnames")
    mon_inc_dir_sub = mon_inc_dir.add_subparsers(dest="include_dirnames_op", required=False)
    mon_inc_dir.set_defaults(func=monitor_include_dirnames_default)
    mon_inc_dir_add = mon_inc_dir_sub.add_parser("add", help="Add directory name(s) to include_dirnames")
    mon_inc_dir_add.add_argument("dirnames", nargs='+', help="Directory name(s) to force-include (e.g., _inbox)")
    mon_inc_dir_add.set_defaults(func=monitor_include_dirnames_add)
    mon_inc_dir_remove = mon_inc_dir_sub.add_parser("remove", help="Remove directory name(s) from include_dirnames")
    mon_inc_dir_remove.add_argument("dirnames", nargs='+', help="Directory name(s) to remove")
    mon_inc_dir_remove.set_defaults(func=monitor_include_dirnames_remove)

    # monitor exclude_dirnames
    mon_exc_dir = monsub.add_parser("exclude_dirnames", help="Manage exclude_dirnames")
    mon_exc_dir_sub = mon_exc_dir.add_subparsers(dest="exclude_dirnames_op", required=False)
    mon_exc_dir.set_defaults(func=monitor_exclude_dirnames_default)
    mon_exc_dir_add = mon_exc_dir_sub.add_parser("add", help="Add directory name(s) to exclude_dirnames")
    mon_exc_dir_add.add_argument("dirnames", nargs='+', help="Directory name(s) to always exclude (e.g., node_modules)")
    mon_exc_dir_add.set_defaults(func=monitor_exclude_dirnames_add)
    mon_exc_dir_remove = mon_exc_dir_sub.add_parser("remove", help="Remove directory name(s) from exclude_dirnames")
    mon_exc_dir_remove.add_argument("dirnames", nargs='+', help="Directory name(s) to remove")
    mon_exc_dir_remove.set_defaults(func=monitor_exclude_dirnames_remove)

    # monitor include_globs
    mon_inc_glob = monsub.add_parser("include_globs", help="Manage include_globs")
    mon_inc_glob_sub = mon_inc_glob.add_subparsers(dest="include_globs_op", required=False)
    mon_inc_glob.set_defaults(func=monitor_include_globs_default)
    mon_inc_glob_add = mon_inc_glob_sub.add_parser("add", help="Add glob pattern(s) to include_globs")
    mon_inc_glob_add.add_argument("patterns", nargs='+', help="Glob pattern(s) to override exclusions (e.g., */_inbox/**)")
    mon_inc_glob_add.set_defaults(func=monitor_include_globs_add)
    mon_inc_glob_remove = mon_inc_glob_sub.add_parser("remove", help="Remove glob pattern(s) from include_globs")
    mon_inc_glob_remove.add_argument("patterns", nargs='+', help="Pattern(s) to remove")
    mon_inc_glob_remove.set_defaults(func=monitor_include_globs_remove)

    # monitor exclude_globs
    mon_exc_glob = monsub.add_parser("exclude_globs", help="Manage exclude_globs")
    mon_exc_glob_sub = mon_exc_glob.add_subparsers(dest="exclude_globs_op", required=False)
    mon_exc_glob.set_defaults(func=monitor_exclude_globs_default)
    mon_exc_glob_add = mon_exc_glob_sub.add_parser("add", help="Add glob pattern(s) to exclude_globs")
    mon_exc_glob_add.add_argument("patterns", nargs='+', help="Glob pattern(s) to exclude (e.g., **/_build/**)")
    mon_exc_glob_add.set_defaults(func=monitor_exclude_globs_add)
    mon_exc_glob_remove = mon_exc_glob_sub.add_parser("remove", help="Remove glob pattern(s) from exclude_globs")
    mon_exc_glob_remove.add_argument("patterns", nargs='+', help="Pattern(s) to remove")
    mon_exc_glob_remove.set_defaults(func=monitor_exclude_globs_remove)

    # monitor managed
    mon_managed = monsub.add_parser("managed", help="Manage managed_directories with priorities")
    mon_managed_sub = mon_managed.add_subparsers(dest="managed_op", required=False)
    mon_managed.set_defaults(func=monitor_managed_default)
    mon_managed_add = mon_managed_sub.add_parser("add", help="Add managed directory with priority")
    mon_managed_add.add_argument("path", help="Directory path")
    mon_managed_add.add_argument("--priority", type=int, required=True, help="Priority score (e.g., 100)")
    mon_managed_add.set_defaults(func=monitor_managed_add)
    mon_managed_remove = mon_managed_sub.add_parser("remove", help="Remove managed directory")
    mon_managed_remove.add_argument("path", help="Directory path to remove")
    mon_managed_remove.set_defaults(func=monitor_managed_remove)
    mon_managed_priority = mon_managed_sub.add_parser("set-priority", help="Set priority for managed directory")
    mon_managed_priority.add_argument("path", help="Directory path")
    mon_managed_priority.add_argument("priority", type=int, help="New priority score")
    mon_managed_priority.set_defaults(func=monitor_managed_priority)
