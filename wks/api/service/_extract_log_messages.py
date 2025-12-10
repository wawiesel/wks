"""Extract warnings and errors from service log (UNO: single function)."""

from pathlib import Path
from typing import Tuple


def extract_log_messages(log_path: Path) -> Tuple[list[str], list[str]]:
    """Return (warnings, errors) parsed from log file."""
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

