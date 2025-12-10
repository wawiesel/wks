"""Daemon run command - runs the daemon in the foreground."""

import os
from pathlib import Path

from ..config.WKSConfig import WKSConfig
from .Daemon import Daemon
from ._pid_running import _pid_running


def cmd_run(restrict_dir: Path | None = None) -> None:
    """Run the daemon in the foreground.

    Args:
        restrict_dir: Optional directory to restrict monitoring to. If None, uses configured paths.

    Raises:
        RuntimeError: If daemon is already running for this configuration or other error occurs.
    """
    # Load configuration
    config = WKSConfig.load()
    config_label = config.daemon.data.label  # Get label from config (per-config identifier)

    # Check if daemon is already running for this configuration
    home_dir = WKSConfig.get_home_dir()
    lock_file = home_dir / "daemon.lock"
    if lock_file.exists():
        try:
            lock_content = lock_file.read_text().strip()
            if lock_content:
                lines = lock_content.splitlines()
                if len(lines) >= 2:
                    # Lock file format: PID on first line, label on second line
                    lock_pid = int(lines[0])
                    lock_label = lines[1]
                    # Only consider it running if label matches (same config)
                    if lock_label == config_label and _pid_running(lock_pid):
                        raise RuntimeError(f"Daemon is already running for this configuration (PID: {lock_pid}, label: {config_label}, lock file: {lock_file})")
                else:
                    # Old format or invalid, try to parse as just PID
                    try:
                        lock_pid = int(lines[0])
                        if _pid_running(lock_pid):
                            # Stale lock from old format, remove it
                            lock_file.unlink()
                    except (ValueError, IndexError):
                        # Invalid lock file, remove it
                        lock_file.unlink()
        except Exception:
            # Invalid lock file, remove it
            lock_file.unlink()

    # Check service status (if service is installed for this config)
    try:
        with Daemon(config.daemon) as daemon:
            service_status = daemon.get_service_status()
            # Verify service label matches config label
            if service_status.get("installed") and service_status.get("label") == config_label:
                if "pid" in service_status:
                    pid = service_status["pid"]
                    if _pid_running(pid):
                        raise RuntimeError(f"Daemon service is already running for this configuration (PID: {pid}, label: {config_label})")
    except (NotImplementedError, Exception):
        # Service status not supported or error, continue
        pass

    # Create lock file (per-config instance)
    home_dir = WKSConfig.get_home_dir()
    lock_file = home_dir / "daemon.lock"
    try:
        # Lock file format: PID on first line, label on second line
        lock_file.write_text(f"{os.getpid()}\n{config_label}")
    except Exception as e:
        raise RuntimeError(f"Failed to create lock file: {e}") from e

    try:
        # Run daemon
        with Daemon(config.daemon) as daemon:
            daemon.run(restrict_dir=restrict_dir)
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        pass
    finally:
        # Remove lock file
        if lock_file.exists():
            lock_file.unlink()

