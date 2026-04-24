from __future__ import annotations

import shutil
from contextlib import suppress
from pathlib import Path

from ..config.WKSConfig import WKSConfig


def resolve_wksc_path() -> str:
    wksc_path = shutil.which("wksc")
    if not wksc_path:
        raise RuntimeError("wksc command not found in PATH. Ensure WKS is installed.")
    return wksc_path


def prepare_service_home() -> tuple[Path, Path]:
    working_directory = WKSConfig.get_home_dir()
    log_file = working_directory / "logs" / "service.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    working_directory.mkdir(parents=True, exist_ok=True)
    return working_directory, log_file


def remove_daemon_lock() -> None:
    lock_path = WKSConfig.get_home_dir() / "daemon.lock"
    if lock_path.exists():
        with suppress(Exception):
            lock_path.unlink()
