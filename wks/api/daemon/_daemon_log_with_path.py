from pathlib import Path

from ..log.append_log import append_log


# Redefining helper to take path
def _daemon_log_with_path(log_path: Path, level: str, message: str) -> None:
    append_log(log_path, "daemon", level, message)
