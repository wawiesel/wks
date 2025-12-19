import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Prevent multiple configurations
_CONFIGURED = False


def configure_logging(wks_home: Path | None = None) -> None:
    """Configure unified WKS logging.

    Args:
        wks_home: Path to WKS home directory. If None, derived from environment.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    if wks_home is None:
        env_home = os.environ.get("WKS_HOME")
        wks_home = Path(env_home).expanduser().resolve() if env_home else Path.home() / ".wks"

    # Ensure directory exists
    wks_home.mkdir(parents=True, exist_ok=True)
    log_file = wks_home / "wks.log"

    root_logger = logging.getLogger("wks")
    root_logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File Handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,  # 5MB * 3
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Ensures logging is configured (lazy init if needed, though explicit config preferred at app entry).
    """
    if not _CONFIGURED:
        configure_logging()

    return logging.getLogger(f"wks.{name}")
