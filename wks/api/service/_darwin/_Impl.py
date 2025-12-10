"""macOS service implementation."""

import os
import subprocess
import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .._AbstractImpl import _AbstractImpl
from ..ServiceConfig import ServiceConfig
from ..FilesystemEvents import FilesystemEvents
from ...config.WKSConfig import WKSConfig
from ._Data import _Data


class _Impl(_AbstractImpl):
    """macOS-specific service implementation."""

    @staticmethod
    def _get_launch_agents_dir() -> Path:
        """Get the LaunchAgents directory for the current user."""
        return Path.home() / "Library" / "LaunchAgents"

    @staticmethod
    def _get_plist_path(label: str) -> Path:
        """Get the plist file path for a given label."""
        return _Impl._get_launch_agents_dir() / f"{label}.plist"

    @staticmethod
    def _create_plist_content(config: _Data, python_path: str, module_path: str, project_root: Path, restrict_dir: Path | None = None) -> str:
        """Create launchd plist XML content.

        Args:
            config: Daemon configuration data
            python_path: Path to Python interpreter
            module_path: Python module path to run
            project_root: Project root directory for PYTHONPATH
            restrict_dir: Optional directory to restrict monitoring to (stored as environment variable)
        """
        # Working directory is always WKS_HOME
        working_directory = WKSConfig.get_home_dir()

        # Single standardized log file under WKS_HOME
        log_file = working_directory / "logs" / "service.log"

        # Ensure directories exist
        log_file.parent.mkdir(parents=True, exist_ok=True)
        working_directory.mkdir(parents=True, exist_ok=True)

        # Build environment variables
        env_vars = f"""    <key>PYTHONPATH</key>
    <string>{str(project_root)}</string>"""
        if restrict_dir is not None:
            restrict_path = str(restrict_dir.expanduser().resolve())
            env_vars += f"""
    <key>WKS_SERVICE_RESTRICT_DIR</key>
    <string>{restrict_path}</string>"""

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
{env_vars}
  </dict>
  <key>RunAtLoad</key>
  <{'true' if config.run_at_load else 'false'}/>
  <key>KeepAlive</key>
  <{'true' if config.keep_alive else 'false'}/>
  <key>StandardOutPath</key>
  <string>{log_file}</string>
  <key>StandardErrorPath</key>
  <string>{log_file}</string>
</dict>
</plist>"""
        return plist

    def __init__(self, service_config: ServiceConfig | None = None):
        """Initialize macOS service implementation.

        Args:
            service_config: Service configuration. If None, loads from WKSConfig.
        """
        if service_config is None:
            config = WKSConfig.load()
            service_config = config.service

        if not isinstance(service_config.data, _Data):
            raise ValueError("macOS service config data is required")
        self.config = service_config
        self._running = False
        self._observer: Observer | None = None
        self._event_handler: "_Impl._ServiceEventHandler" | None = None

    class _ServiceEventHandler(FileSystemEventHandler):
        """Handles filesystem events and accumulates them."""

        def __init__(self):
            super().__init__()
            self._modified: set[str] = set()
            self._created: set[str] = set()
            self._deleted: set[str] = set()
            self._moved: dict[str, str] = {}  # old_path -> new_path

        def on_modified(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._modified.add(event.src_path)

        def on_created(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._created.add(event.src_path)

        def on_deleted(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._deleted.add(event.src_path)

        def on_moved(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._moved[event.src_path] = event.dest_path

        def get_and_clear_events(self) -> FilesystemEvents:
            """Return accumulated events and clear the accumulator."""
            modified = list(self._modified)
            created = list(self._created)
            deleted = list(self._deleted)
            moved = list(self._moved.items())

            self._modified.clear()
            self._created.clear()
            self._deleted.clear()
            self._moved.clear()

            return FilesystemEvents(modified=modified, created=created, deleted=deleted, moved=moved)

    def run(self, restrict_dir: Path | None = None) -> None:
        """Run the service main loop.

        Args:
            restrict_dir: Optional directory to restrict monitoring to. If None, checks environment variable
                WKS_SERVICE_RESTRICT_DIR (set by service), then falls back to configured paths.
        """
        import os
        from ...monitor.cmd_sync import cmd_sync

        self._running = True
        config = WKSConfig.load()
        monitor_cfg = config.monitor

        # Determine paths to watch
        # Priority: 1) restrict_dir parameter, 2) environment variable (from service), 3) configured paths
        if restrict_dir is not None:
            watch_paths = [str(restrict_dir.expanduser().resolve())]
        elif "WKS_SERVICE_RESTRICT_DIR" in os.environ:
            watch_paths = [os.environ["WKS_SERVICE_RESTRICT_DIR"]]
        else:
            watch_paths = [str(Path(p).expanduser().resolve()) for p in monitor_cfg.filter.include_paths]

        # Initialize filesystem watcher
        self._event_handler = self._ServiceEventHandler()
        self._observer = Observer()

        for path_str in watch_paths:
            path = Path(path_str)
            if path.exists():
                self._observer.schedule(self._event_handler, str(path), recursive=True)

        self._observer.start()

        try:
            while self._running:
                # Wait for sync interval
                time.sleep(self.config.sync_interval_secs)

                # Get accumulated events
                events = self._event_handler.get_and_clear_events()

                if events.is_empty():
                    continue

                # TODO: Implement event collapsing here (e.g., self._collapse_events(events))

                # Send events to monitor sync
                for path in events.modified + events.created + events.deleted:
                    cmd_sync(path)
                for old_path, new_path in events.moved:
                    cmd_sync(old_path)  # Treat as delete at old location
                    cmd_sync(new_path)  # Treat as create at new location

        except KeyboardInterrupt:
            pass
        finally:
            if self._observer:
                self._observer.stop()
                self._observer.join()
            self._running = False

    def get_filesystem_events(self) -> FilesystemEvents:
        """Get accumulated filesystem events since last call.

        Returns:
            FilesystemEvents object containing lists of paths for each event type.
        """
        if self._event_handler is None:
            return FilesystemEvents(modified=[], created=[], deleted=[], moved=[])
        return self._event_handler.get_and_clear_events()

    def stop(self) -> None:
        """Stop the daemon gracefully."""
        self._running = False
        if self._observer:
            self._observer.stop()

    def install_service(self, python_path: str, project_root: Path, restrict_dir: Path | None = None) -> dict[str, Any]:
        """Install daemon as macOS launchd service.

        Args:
            python_path: Path to Python interpreter
            project_root: Project root directory for PYTHONPATH
            restrict_dir: Optional directory to restrict monitoring to (stored as environment variable)
        """
        module_path = f"wks.api.daemon._{self.config.type}._Impl"
        plist_path = self._get_plist_path(self.config.data.label)
        plist_dir = plist_path.parent

        # Ensure LaunchAgents directory exists
        plist_dir.mkdir(parents=True, exist_ok=True)

        # Create plist content
        plist_content = self._create_plist_content(self.config.data, python_path, module_path, project_root, restrict_dir=restrict_dir)

        # Write plist file
        plist_path.write_text(plist_content, encoding="utf-8")

        # Check if service is already loaded
        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self.config.data.label}"],
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

        return {
            "success": True,
            "type": "darwin",
            "label": self.config.data.label,
            "plist_path": str(plist_path),
        }

    def uninstall_service(self) -> dict[str, Any]:
        """Uninstall daemon macOS launchd service."""
        plist_path = self._get_plist_path(self.config.data.label)
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

        return {
            "success": True,
            "type": "darwin",
            "label": self.config.data.label,
        }

    def get_service_status(self) -> dict[str, Any]:
        """Get daemon macOS launchd service status."""
        plist_path = self._get_plist_path(self.config.data.label)
        uid = os.getuid()

        status: dict[str, Any] = {
            "installed": plist_path.exists(),
            "plist_path": str(plist_path),
        }

        if status["installed"]:
            try:
                result = subprocess.run(
                    ["launchctl", "print", f"gui/{uid}/{self.config.data.label}"],
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

    def start_service(self) -> dict[str, Any]:
        """Start daemon via macOS launchctl."""
        uid = os.getuid()
        plist_path = self._get_plist_path(self.config.data.label)

        # First check if service is loaded
        try:
            result = subprocess.run(
                ["launchctl", "print", f"gui/{uid}/{self.config.data.label}"],
                capture_output=True,
                text=True,
                check=False,
            )
            service_loaded = result.returncode == 0
        except Exception:
            service_loaded = False

        # If service is not loaded but plist exists, bootstrap it first
        if not service_loaded and plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                # Bootstrap also starts the service, verify it's running
                import time
                time.sleep(0.5)  # Give service a moment to start
                status = self.get_service_status()
                if "pid" in status:
                    return {
                        "success": True,
                        "type": "darwin",
                        "label": self.config.data.label,
                        "action": "bootstrapped",
                        "pid": status["pid"],
                    }
                else:
                    log_path = Path(self.config.data.log_file).expanduser()
                    return {
                        "success": False,
                        "error": f"Service failed to start after bootstrap (no PID found). Check logs at: {log_path}",
                    }
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "error": f"Failed to bootstrap service: {e.stderr}",
                }

        # Service is loaded, use kickstart to start/restart it
        # Note: -k flag kills and restarts if already running, starts if not running
        try:
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{self.config.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            # Verify service actually started by checking for PID
            import time
            time.sleep(0.5)  # Give service a moment to start
            status = self.get_service_status()
            if "pid" in status:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self.config.data.label,
                    "action": "kickstarted",
                    "pid": status["pid"],
                }
            else:
                # Service didn't start - check logs
                log_path = Path(self.config.data.log_file).expanduser()
                return {
                    "success": False,
                    "error": f"Service failed to start (no PID found). Check logs at: {log_path}",
                }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": e.stderr,
            }

    def stop_service(self) -> dict[str, Any]:
        """Stop daemon via macOS launchctl."""
        uid = os.getuid()
        try:
            result = subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{self.config.data.label}"],
                check=True,
                capture_output=True,
                text=True,
            )
            return {
                "success": True,
                "type": "darwin",
                "label": self.config.data.label,
            }
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else ""
            # Check for common "not running" errors - treat as success (idempotent)
            if "No such process" in error_msg or e.returncode == 3:
                return {
                    "success": True,
                    "type": "darwin",
                    "label": self.config.data.label,
                    "note": "Service was not running (already stopped).",
                }
            return {
                "success": False,
                "error": f"Failed to stop service: {error_msg}" if error_msg else "Failed to stop service.",
            }
