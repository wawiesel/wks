"""Unified log utilities for all WKS domains.

Single shared logfile at $WKS_HOME/logfile with format:
[TIMESTAMP] [DOMAIN] LEVEL: message
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Pattern to parse [ISO_TIMESTAMP] [DOMAIN] LEVEL: message
_LOG_PATTERN = re.compile(r"^\[([^\]]+)\]\s*\[(\w+)\]\s*(DEBUG|INFO|WARN|ERROR):\s*(.*)$", re.IGNORECASE)


def get_logfile_path(wks_home: Path) -> Path:
    """Get the unified logfile path."""
    return wks_home / "logfile"


def append_log(wks_home: Path, domain: str, level: str, message: str) -> None:
    """Append a timestamped entry to the unified logfile.

    Args:
        wks_home: WKS home directory
        domain: Domain name (e.g., 'daemon', 'monitor', 'vault')
        level: Log level (DEBUG, INFO, WARN, ERROR)
        message: Log message
    """
    log_path = get_logfile_path(wks_home)
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{timestamp}] [{domain}] {level}: {message}\n")
    except Exception:
        pass  # Logging should never raise


def read_log_entries(
    wks_home: Path,
    debug_retention_days: float = 0.5,
    info_retention_days: float = 1.0,
    warning_retention_days: float = 2.0,
    error_retention_days: float = 7.0,
) -> tuple[list[str], list[str]]:
    """Read log entries, filtering expired ones and returning (warnings, errors).

    This is the prune-on-access contract: expired entries are removed when reading.

    Returns:
        Tuple of (warnings, errors) lists
    """
    log_path = get_logfile_path(wks_home)
    warnings: list[str] = []
    errors: list[str] = []

    if not log_path.exists():
        return warnings, errors

    now = datetime.now(timezone.utc)
    cutoffs = {
        "DEBUG": now - timedelta(days=debug_retention_days),
        "INFO": now - timedelta(days=info_retention_days),
        "WARN": now - timedelta(days=warning_retention_days),
        "ERROR": now - timedelta(days=error_retention_days),
    }

    kept_lines: list[str] = []

    try:
        for line in log_path.read_text(errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            match = _LOG_PATTERN.match(stripped)
            if match:
                timestamp_str = match.group(1)
                level = match.group(3).upper()

                try:
                    entry_time = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    entry_time = now

                cutoff = cutoffs.get(level, now)
                if entry_time < cutoff:
                    continue  # Expired

                kept_lines.append(stripped)
                if level == "ERROR":
                    errors.append(stripped)
                elif level == "WARN":
                    warnings.append(stripped)
            else:
                # Legacy format - keep and categorize
                kept_lines.append(stripped)
                upper = stripped.upper()
                if "ERROR" in upper:
                    errors.append(stripped)
                elif "WARN" in upper:
                    warnings.append(stripped)

        # Write back non-expired entries (prune-on-access)
        log_path.write_text("\n".join(kept_lines) + "\n" if kept_lines else "", encoding="utf-8")
    except Exception:
        pass

    return warnings, errors
