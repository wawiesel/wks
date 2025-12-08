"""macOS launchd service management."""

import os
import subprocess
from pathlib import Path
from typing import Any

from ...daemon._macos._DaemonConfigData import _DaemonConfigData


def _get_launch_agents_dir() -> Path:
    """Get the LaunchAgents directory for the current user."""
    return Path.home() / "Library" / "LaunchAgents"


def _get_plist_path(label: str) -> Path:
    """Get the plist file path for a given label."""
    return _get_launch_agents_dir() / f"{label}.plist"


def _create_plist_content(config: _DaemonConfigData, python_path: str, module_path: str, project_root: Path) -> str:
    """Create launchd plist XML content."""
    from ...config.WKSConfig import WKSConfig

    # Working directory is always WKS_HOME
    working_directory = WKSConfig.get_home_dir()

    # Log files are relative to WKS_HOME
    log_file = working_directory / config.log_file
    error_log_file = working_directory / config.error_log_file

    # Ensure directories exist
    log_file.parent.mkdir(parents=True, exist_ok=True)
    error_log_file.parent.mkdir(parents=True, exist_ok=True)
    working_directory.mkdir(parents=True, exist_ok=True)

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{config.label}</string>
  <key>LimitLoadToSessionType</key>
  <string>Aqua</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_path}</string>
    <string>-m</string>
    <string>{module_path}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{working_directory}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>{str(project_root)}</string>
  </dict>
  <key>RunAtLoad</key>
  <{'true' if config.run_at_load else 'false'}/>
  <key>KeepAlive</key>
  <{'true' if config.keep_alive else 'false'}/>
  <key>StandardOutPath</key>
  <string>{log_file}</string>
  <key>StandardErrorPath</key>
  <string>{error_log_file}</string>
</dict>
</plist>"""
    return plist


def install_service(config: _DaemonConfigData, python_path: str, module_path: str, project_root: Path) -> None:
    """Install launchd service.

    Args:
        config: macOS daemon configuration
        python_path: Path to Python interpreter
        module_path: Python module to run (e.g., "wks.daemon")
        project_root: Project root directory for PYTHONPATH

    Raises:
        RuntimeError: If installation fails
    """
    plist_path = _get_plist_path(config.label)
    plist_dir = plist_path.parent

    # Ensure LaunchAgents directory exists
    plist_dir.mkdir(parents=True, exist_ok=True)

    # Create plist content
    plist_content = _create_plist_content(config, python_path, module_path, project_root)

    # Write plist file
    plist_path.write_text(plist_content, encoding="utf-8")

    # Check if service is already loaded
    uid = os.getuid()
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{config.label}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            raise RuntimeError(f"Service is already installed and loaded. Use 'wksc daemon uninstall' first, or 'wksc daemon reinstall' to reinstall.")
    except RuntimeError:
        raise  # Re-raise our error
    except Exception:
        pass  # If check fails, proceed with bootstrap

    # Load service with launchctl
    try:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to load launchd service: {e.stderr}") from e


def uninstall_service(config: _DaemonConfigData) -> None:
    """Uninstall launchd service.

    Args:
        config: macOS daemon configuration

    Raises:
        RuntimeError: If uninstallation fails
    """
    plist_path = _get_plist_path(config.label)
    uid = os.getuid()

    # Unload service
    try:
        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(plist_path)],
            check=False,  # Don't fail if already unloaded
            capture_output=True,
            text=True,
        )
    except Exception:
        pass  # Ignore errors during unload

    # Remove plist file
    if plist_path.exists():
        plist_path.unlink()


def is_installed(config: _DaemonConfigData) -> bool:
    """Check if service is installed.

    Args:
        config: macOS daemon configuration

    Returns:
        True if plist file exists
    """
    return _get_plist_path(config.label).exists()


def get_service_status(config: _DaemonConfigData) -> dict[str, Any]:
    """Get launchd service status.

    Args:
        config: macOS daemon configuration

    Returns:
        Dictionary with status information
    """
    plist_path = _get_plist_path(config.label)
    uid = os.getuid()

    status: dict[str, Any] = {
        "installed": plist_path.exists(),
        "plist_path": str(plist_path),
    }

    if status["installed"]:
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{config.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # Parse output for PID
                for line in result.stdout.splitlines():
                    if line.strip().startswith("pid ="):
                        try:
                            status["pid"] = int(line.split("=", 1)[1].strip())
                        except (ValueError, IndexError):
                            pass
        except Exception:
            pass

    return status
