from datetime import datetime, timezone
from pathlib import Path


def append_log(log_path: Path, domain: str, level: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{timestamp}] [{domain}] {level}: {message}\n")
    except OSError:
        pass
