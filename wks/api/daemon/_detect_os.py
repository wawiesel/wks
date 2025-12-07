"""Detect operating system for daemon installation."""

import platform


def detect_os() -> str:
    """Detect the current operating system.

    Returns:
        OS identifier string: "macos", "linux", "windows", or "unknown"

    Raises:
        RuntimeError: If OS cannot be determined
    """
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    raise RuntimeError(f"Unsupported operating system: {system}")

