"""Check if a process ID is running."""

import os


def _pid_running(pid: int) -> bool:
    """Check if a process ID is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False
