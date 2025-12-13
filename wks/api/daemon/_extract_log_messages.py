"""Extract warnings and errors from a single log file (UNO: single function)."""

from pathlib import Path


def extract_log_messages(log_path: Path) -> tuple[list[str], list[str]]:
    """Return (warnings, errors) lists parsed from the log file."""
    warnings: list[str] = []
    errors: list[str] = []
    if not log_path or not log_path.exists():
        return warnings, errors

    try:
        for line in log_path.read_text(errors="ignore").splitlines():
            upper = line.upper()
            if "ERROR" in upper:
                errors.append(line.strip())
            elif "WARN" in upper:
                warnings.append(line.strip())
    except Exception:
        pass
    return warnings, errors
