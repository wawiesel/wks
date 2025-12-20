from datetime import datetime, timezone
from pathlib import Path


def append_log(log_path: Path, domain: str, level: str, message: str) -> None:
    """Append a timestamped entry to the unified logfile.

    Args:
        log_path: Path to the logfile
        domain: Domain name (e.g., 'daemon', 'monitor', 'vault')
        level: Log level (DEBUG, INFO, WARN, ERROR)
        message: Log message
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{timestamp}] [{domain}] {level}: {message}\n")
    except Exception:
        pass  # Logging should never raise
