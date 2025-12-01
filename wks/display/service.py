"""Service status display helpers.

Display functions accept dataclasses from service_controller, not dicts.
Use to_dict() only at JSON serialization boundaries.
"""

from typing import Any, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..service_controller import ServiceStatusData, ServiceStatusLaunch


def fmt_bool(value: Optional[bool], color: bool = False) -> str:
    """Format a boolean for display.
    
    Args:
        value: Boolean value or None
        color: If True, wrap in Rich color markup
    
    Returns:
        Formatted string: "true", "false", or "-" for None
    """
    if value is None:
        return "-"
    if color:
        return "[green]true[/green]" if value else "[red]false[/red]"
    return "true" if value else "false"


def format_timestamp(value: Optional[Any], fmt: str) -> str:
    """Format a timestamp value for display.
    
    Args:
        value: Timestamp string (ISO format) or None
        fmt: strftime format string
    
    Returns:
        Formatted timestamp or original text on parse failure
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    
    from datetime import datetime
    
    # Try ISO format parsing
    try:
        s = text
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except Exception:
        # Fallback: try without T separator
        try:
            fallback = text.replace("T", " ").replace("Z", "")
            dt = datetime.fromisoformat(fallback)
        except Exception:
            return text
    
    return dt.strftime(fmt)


def build_status_rows(status: "ServiceStatusData") -> List[Tuple[str, str]]:
    """Build display rows from ServiceStatusData dataclass.
    
    Args:
        status: ServiceStatusData dataclass instance
    
    Returns:
        List of (label, value) tuples for table display
    """
    rows: List[Tuple[str, str]] = []
    
    # Health section
    rows.append(("[bold cyan]Health[/bold cyan]", ""))
    rows.append(("  Running", fmt_bool(status.running, color=True)))
    rows.append(("  Uptime", status.uptime or "-"))
    rows.append(("  PID", str(status.pid) if status.pid is not None else "-"))
    rows.append(("  OK", fmt_bool(status.ok, color=True)))
    rows.append(("  Lock", fmt_bool(status.lock, color=True)))
    
    # Launch type from launch agent or default
    launch_type = status.launch.type if status.launch.present() else "LaunchAgent"
    rows.append(("  Type", launch_type or "LaunchAgent"))
    
    # File System section
    rows.append(("[bold cyan]File System[/bold cyan]", ""))
    rows.append(("  Pending deletes", str(status.pending_deletes) if status.pending_deletes is not None else "-"))
    rows.append(("  Pending mods", str(status.pending_mods) if status.pending_mods is not None else "-"))
    
    if status.fs_rate_weighted is not None:
        rows.append(("  Ops (last min)", str(int(status.fs_rate_weighted * 60))))
    if status.fs_rate_short is not None:
        rows.append(("  Ops/sec (10s)", f"{status.fs_rate_short:.2f}"))
    if status.fs_rate_long is not None:
        rows.append(("  Ops/sec (10m)", f"{status.fs_rate_long:.2f}"))
    if status.fs_rate_weighted is not None:
        rows.append(("  Ops/sec (weighted)", f"{status.fs_rate_weighted:.2f}"))
    
    # Launch section (only if present)
    if status.launch.present():
        rows.append(("[bold cyan]Launch[/bold cyan]", ""))
        rows.append(("  Program", status.launch.arguments or status.launch.program or "-"))
        rows.append(("  Stdout", status.launch.stdout or "-"))
        rows.append(("  Stderr", status.launch.stderr or "-"))
        rows.append(("  Path", status.launch.path or "-"))
        rows.append(("  Type", status.launch.type or "-"))
    
    return rows

