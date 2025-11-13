"""Monitor commands - filesystem monitoring status and configuration (Monitor Layer)."""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ...config import get_config_path, load_config
from ...constants import MAX_DISPLAY_WIDTH
from ...monitor_controller import MonitorController, MonitorValidator
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


def build_ignore_rules_rows(status_data) -> List[Dict[str, str]]:
    """Build table rows for ignore rules (ignore_dirnames and ignore_globs)."""
    rows = []
    ignore_dirnames = status_data.ignore_dirnames
    ignore_globs = status_data.ignore_globs

    styled_ignore_dirnames = style_setting_column("[bold cyan]ignore_dirnames[/bold cyan]")
    rows.append({
        "Ignore Rule": styled_ignore_dirnames,
        "Count": str(len(ignore_dirnames))
    })
    rows.append({"Ignore Rule": "", "Count": ""})

    for dirname in ignore_dirnames:
        validation_info = status_data.ignore_dirname_validation.get(dirname, {})
        error_msg = validation_info.get("error")
        is_valid = validation_info.get("valid", True)
        styled_dirname = style_setting_column(f"  {dirname}")
        rows.append({
            "Ignore Rule": styled_dirname,
            "Count": MonitorValidator.status_symbol(error_msg, is_valid)
        })

    rows.append({"Ignore Rule": "", "Count": ""})
    styled_ignore_globs = style_setting_column("[bold cyan]ignore_globs[/bold cyan]")
    rows.append({
        "Ignore Rule": styled_ignore_globs,
        "Count": str(len(ignore_globs))
    })

    for glob_pattern in ignore_globs:
        validation_info = status_data.ignore_glob_validation.get(glob_pattern, {})
        error_msg = validation_info.get("error")
        is_valid = validation_info.get("valid", True)
        styled_pattern = style_setting_column(f"  {glob_pattern}")
        rows.append({
            "Ignore Rule": styled_pattern,
            "Count": MonitorValidator.status_symbol(error_msg, is_valid)
        })

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
        from ...monitor_controller import MonitorConfig

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
    # Color constants for consistent styling
    COLOR_FILES_KEY = "bold purple"
    COLOR_FILES_VALUE = "purple"
    COLOR_LAST_TOUCH_KEY = "bold green"
    COLOR_LAST_TOUCH_VALUE = "green"
    COLOR_HEADING = "bold cyan"
    COLOR_PATH_BG = "on gray30"

    # Get last touch time
    last_touch = get_last_touch_time(config) or "Never"

    rows = []
    # Add files and last touch at the top
    rows.append((f"[{COLOR_FILES_KEY}]files[/{COLOR_FILES_KEY}]", f"[{COLOR_FILES_VALUE}]{str(total_files)}[/{COLOR_FILES_VALUE}]"))
    rows.append((f"[{COLOR_LAST_TOUCH_KEY}]last touch[/{COLOR_LAST_TOUCH_KEY}]", f"[{COLOR_LAST_TOUCH_VALUE}]{last_touch}[/{COLOR_LAST_TOUCH_VALUE}]"))
    rows.append(("", ""))  # Empty row separator

    # Managed directories
    rows.append((f"[{COLOR_HEADING}]managed_directories[/{COLOR_HEADING}]", str(len(managed_dirs_dict))))
    red_paths, yellow_paths = build_problematic_paths(issues, redundancies, managed_dirs_dict, include_paths, exclude_paths)
    max_pip_count, max_num_width = calculate_priority_alignment(managed_dirs_dict)

    # Ensure we have minimum values to avoid division by zero
    max_pip_count = max(max_pip_count, 1)
    max_num_width = max(max_num_width, 1)

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

    # Include paths
    rows.append((f"[{COLOR_HEADING}]include_paths[/{COLOR_HEADING}]", str(len(include_paths))))
    for path in sorted(include_paths):
        error_msg = None if path not in (red_paths | yellow_paths) else "issue"
        is_valid = path not in red_paths
        rows.append((f"  [{COLOR_PATH_BG}]{path}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    rows.append(("", ""))

    # Exclude paths
    rows.append((f"[{COLOR_HEADING}]exclude_paths[/{COLOR_HEADING}]", str(len(exclude_paths))))
    for path in sorted(exclude_paths):
        error_msg = None if path not in (red_paths | yellow_paths) else "issue"
        is_valid = path not in red_paths
        rows.append((f"  [{COLOR_PATH_BG}]{path}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    rows.append(("", ""))

    # Ignore rules
    rows.append((f"[{COLOR_HEADING}]ignore_dirnames[/{COLOR_HEADING}]", str(len(status_data.ignore_dirnames))))
    for dirname in status_data.ignore_dirnames:
        validation_info = status_data.ignore_dirname_validation.get(dirname, {})
        error_msg = validation_info.get("error")
        is_valid = validation_info.get("valid", True)
        rows.append((f"  [{COLOR_PATH_BG}]{dirname}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    rows.append(("", ""))
    rows.append((f"[{COLOR_HEADING}]ignore_globs[/{COLOR_HEADING}]", str(len(status_data.ignore_globs))))
    for glob_pattern in status_data.ignore_globs:
        validation_info = status_data.ignore_glob_validation.get(glob_pattern, {})
        error_msg = validation_info.get("error")
        is_valid = validation_info.get("valid", True)
        rows.append((f"  [{COLOR_PATH_BG}]{glob_pattern}[/{COLOR_PATH_BG}]", MonitorValidator.status_symbol(error_msg, is_valid)))

    return rows


def display_monitor_status_table(
    display: Any,
    monitor_status_rows: List[Tuple[str, str]]
) -> None:
    """Display the monitor status table using reflowing two-column layout.

    Args:
        display: Display object for rendering
        monitor_status_rows: List of (key, value) tuples for monitor status data
    """
    from rich.table import Table
    from rich.panel import Panel
    from rich.style import Style

    key_width = 22  # ~22 chars for key
    value_width = 10  # ~10 chars for value

    from rich.columns import Columns

    # Create individual table rows that will reflow into columns
    # Apply grey30 background to keys
    row_tables = []
    for key, value in monitor_status_rows:
        row_table = Table(show_header=False, box=None, padding=(0, 1))
        row_table.add_column("Key", justify="left", width=key_width)
        row_table.add_column("Value", justify="right", width=value_width)
        row_table.add_row(key, value)
        row_tables.append(row_table)
    # Use Columns with column_first=True for reflow layout
    # This will fill the first column, then the second column
    columns = Columns(row_tables, equal=True, column_first=True)

    # Display Monitor Status panel (without Tracked Files)
    # Don't set explicit width to let Rich calculate based on content
    panel = Panel.fit(columns, title="Monitor Status", border_style="cyan")
    display.console.print(panel)


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
    monitor_config = cfg.get("monitor", {})

    include_paths = set(monitor_config.get("include_paths", []))
    exclude_paths = set(monitor_config.get("exclude_paths", []))
    managed_dirs = set(monitor_config.get("managed_directories", {}).keys())

    issues = check_path_conflicts(include_paths, exclude_paths)
    warnings = check_duplicate_managed_dirs(managed_dirs)

    return display_validation_results(display, issues, warnings)


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
    return value, value


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
    if list_name == "ignore_dirnames":
        ignore_globs = cfg["monitor"].get("ignore_globs", [])
        is_valid, error_msg = MonitorValidator.validate_ignore_dirname(
            value_resolved if not resolve_path else value,
            ignore_globs
        )
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
    config_path = get_config_path()

    if not config_path.exists():
        display.error(f"Config file not found: {config_path}")
        return 2

    # Read current config
    with open(config_path) as f:
        cfg = json.load(f)

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
    monitor_config = cfg.get("monitor", {})
    items = monitor_config.get(list_name, [])

    if not items:
        display.info(f"No {list_name} configured")
        return 0

    # Get other config items for validation
    ignore_globs = monitor_config.get("ignore_globs", [])
    ignore_dirnames = monitor_config.get("ignore_dirnames", [])
    include_paths = monitor_config.get("include_paths", [])
    exclude_paths = monitor_config.get("exclude_paths", [])
    managed_dirs = monitor_config.get("managed_directories", {})

    table_data = []
    for i, item in enumerate(items, 1):
        is_valid, error_msg = True, None

        if list_name == "ignore_dirnames":
            is_valid, error_msg = MonitorValidator.validate_ignore_dirname(item, ignore_globs)
        elif list_name == "ignore_globs":
            is_valid, error_msg = MonitorValidator.validate_ignore_glob(item)
        elif list_name in ("include_paths", "exclude_paths"):
            try:
                path_obj = Path(item).expanduser().resolve()
                if not path_obj.exists():
                    is_valid = list_name == "exclude_paths"  # Warning for exclude, error for include
                    error_msg = "Path does not exist" + (" (will be ignored if created)" if is_valid else "")
                elif not path_obj.is_dir():
                    is_valid, error_msg = False, "Not a directory"
            except Exception as e:
                is_valid, error_msg = False, f"Invalid path: {e}"

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


def monitor_ignore_dir_default(args: argparse.Namespace) -> int:
    """Default action for ignore_dirnames: show list."""
    if not args.ignore_dirnames_op:
        return show_monitor_list(args.display_obj, "ignore_dirnames", "Ignore Directory Names")
    return 0


def monitor_ignore_dir_add(args: argparse.Namespace) -> int:
    """Add directory name(s) to ignore_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "ignore_dirnames", dirname, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_ignore_dir_remove(args: argparse.Namespace) -> int:
    """Remove directory name(s) from ignore_dirnames."""
    for dirname in args.dirnames:
        result = modify_monitor_list(args.display_obj, "ignore_dirnames", dirname, "remove", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_ignore_glob_default(args: argparse.Namespace) -> int:
    """Default action for ignore_globs: show list."""
    if not args.ignore_globs_op:
        return show_monitor_list(args.display_obj, "ignore_globs", "Ignore Glob Patterns")
    return 0


def monitor_ignore_glob_add(args: argparse.Namespace) -> int:
    """Add glob pattern(s) to ignore_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "ignore_globs", pattern, "add", resolve_path=False)
        if result != 0:
            return result
    return 0


def monitor_ignore_glob_remove(args: argparse.Namespace) -> int:
    """Remove glob pattern(s) from ignore_globs."""
    for pattern in args.patterns:
        result = modify_monitor_list(args.display_obj, "ignore_globs", pattern, "remove", resolve_path=False)
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

    # monitor status
    monstatus = monsub.add_parser("status", help="Show monitoring statistics")
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

    # monitor ignore_dirnames
    mon_ignore_dir = monsub.add_parser("ignore_dirnames", help="Manage ignore_dirnames")
    mon_ignore_dir_sub = mon_ignore_dir.add_subparsers(dest="ignore_dirnames_op", required=False)
    mon_ignore_dir.set_defaults(func=monitor_ignore_dir_default)
    mon_ignore_dir_add = mon_ignore_dir_sub.add_parser("add", help="Add directory name(s) to ignore_dirnames")
    mon_ignore_dir_add.add_argument("dirnames", nargs='+', help="Directory name(s) to ignore (e.g., node_modules)")
    mon_ignore_dir_add.set_defaults(func=monitor_ignore_dir_add)
    mon_ignore_dir_remove = mon_ignore_dir_sub.add_parser("remove", help="Remove directory name(s) from ignore_dirnames")
    mon_ignore_dir_remove.add_argument("dirnames", nargs='+', help="Directory name(s) to remove")
    mon_ignore_dir_remove.set_defaults(func=monitor_ignore_dir_remove)

    # monitor ignore_globs
    mon_ignore_glob = monsub.add_parser("ignore_globs", help="Manage ignore_globs")
    mon_ignore_glob_sub = mon_ignore_glob.add_subparsers(dest="ignore_globs_op", required=False)
    mon_ignore_glob.set_defaults(func=monitor_ignore_glob_default)
    mon_ignore_glob_add = mon_ignore_glob_sub.add_parser("add", help="Add glob pattern(s) to ignore_globs")
    mon_ignore_glob_add.add_argument("patterns", nargs='+', help="Glob pattern(s) to ignore (e.g., *.tmp)")
    mon_ignore_glob_add.set_defaults(func=monitor_ignore_glob_add)
    mon_ignore_glob_remove = mon_ignore_glob_sub.add_parser("remove", help="Remove glob pattern(s) from ignore_globs")
    mon_ignore_glob_remove.add_argument("patterns", nargs='+', help="Pattern(s) to remove")
    mon_ignore_glob_remove.set_defaults(func=monitor_ignore_glob_remove)

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
