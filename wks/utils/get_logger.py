import logging

from .configure_logging import _CONFIGURED, configure_logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name.

    Ensures logging is configured (lazy init if needed, though explicit config preferred at app entry).
    """
    if not _CONFIGURED:
        configure_logging()

    return logging.getLogger(f"wks.{name}")
