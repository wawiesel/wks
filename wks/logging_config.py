"""Centralized logging configuration for WKS."""

import logging
import sys
from pathlib import Path
from typing import Optional

from .utils import wks_home_path


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Configure structured logging for WKS.

    Args:
        level: Logging level (default INFO)
        log_file: Optional path to log file (default ~/.wks/wks.log)
        format_string: Optional custom format string
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    if log_file is None:
        log_file = wks_home_path("wks.log")

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )

    # Suppress noisy third-party loggers
    logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
    logging.getLogger('docling').setLevel(logging.WARNING)
    logging.getLogger('pymongo').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(f"wks.{name}")
