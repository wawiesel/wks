from datetime import datetime, timedelta, timezone
from pathlib import Path

from .LOG_PATTERN import LOG_PATTERN


def read_log_entries(
    log_path: Path,
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

            match = LOG_PATTERN.match(stripped)
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
