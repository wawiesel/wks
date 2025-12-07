"""
File system monitoring for WKS using watchdog.
Monitors directories and tracks file changes without external dependencies.
"""

import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from watchdog.observers import Observer

from ...utils.constants import WKS_HOME_EXT

try:
    from watchdog.observers.fsevents import FSEventsObserver  # macOS
except Exception:  # pragma: no cover
    FSEventsObserver = None  # type: ignore
try:
    from watchdog.observers.kqueue import KqueueObserver  # BSD/macOS
except Exception:  # pragma: no cover
    KqueueObserver = None  # type: ignore
try:
    from watchdog.observers.polling import PollingObserver  # cross-platform
except Exception:  # pragma: no cover
    PollingObserver = None  # type: ignore
import contextlib

from watchdog.events import FileSystemEvent, FileSystemEventHandler


class WKSFileMonitor(FileSystemEventHandler):
    """
    Monitor file system changes and track them for WKS.

    This replaces the A_GIS MongoDB-based monitoring with a simpler
    JSON-based tracking system suitable for personal use.
    """

    def __init__(
        self,
        state_file: Path,
        monitor_config: Any,  # MonitorConfig from wks.api.monitor
        on_change: Callable[[str, str | tuple[str, str]], None] | None = None,
    ):
        """
        Initialize the file monitor.

        Args:
            state_file: Path to JSON file for tracking state
            monitor_config: MonitorConfig instance for path filtering
            on_change: Callback function(event_type, file_path) when files change
        """
        super().__init__()
        self.state_file = Path(state_file)
        self.on_change = on_change
        self.monitor_config = monitor_config
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with self.state_file.open() as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                # State file corrupted, back it up and start fresh
                backup_file = self.state_file.with_suffix(".json.backup")
                try:
                    self.state_file.rename(backup_file)
                    print(f"Warning: Corrupted state file backed up to {backup_file}")
                except OSError:
                    pass
        return {"files": {}, "last_update": None}

    def _save_state(self):
        """Save state to JSON file."""
        self.state["last_update"] = datetime.now().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w") as f:
            json.dump(self.state, f, indent=2)

    def _should_ignore(self, path: str | bytes) -> bool:
        """Check if path should be ignored based on monitor rules."""
        try:
            path_str = path.decode() if isinstance(path, bytes) else path
            from .api.monitor.explain_path import explain_path

            allowed, _ = explain_path(self.monitor_config, Path(path_str))
            return not allowed
        except Exception:
            return False

    def _track_change(self, event_type: str, path: str | bytes):
        """Track a file change in state."""
        if self._should_ignore(path):
            return

        path_str = str(Path(path.decode() if isinstance(path, bytes) else path).resolve())

        if path_str not in self.state["files"]:
            self.state["files"][path_str] = {
                "created": datetime.now().isoformat(),
                "modifications": [],
            }

        self.state["files"][path_str]["modifications"].append(
            {"type": event_type, "timestamp": datetime.now().isoformat()}
        )

        # Keep only last 10 modifications per file
        if len(self.state["files"][path_str]["modifications"]) > 10:
            self.state["files"][path_str]["modifications"] = self.state["files"][path_str]["modifications"][-10:]

        self._save_state()

        if self.on_change:
            self.on_change(event_type, path_str)

    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation."""
        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path
        if not event.is_directory:
            self._track_change("created", src_path)
        else:
            # Emit callback for directory creation so higher layers can react (e.g., project notes)
            if self.on_change and not self._should_ignore(src_path):
                with contextlib.suppress(Exception):
                    self.on_change("created", src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        if not event.is_directory:
            src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path
            self._track_change("modified", src_path)

    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move."""
        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path
        dest_path = event.dest_path.decode() if isinstance(event.dest_path, bytes) else event.dest_path
        # Track the move with both paths for files; emit callback for all
        if self._should_ignore(src_path) or self._should_ignore(dest_path):
            return

        src_str = str(Path(src_path).resolve())
        dest_str = str(Path(dest_path).resolve())

        if not event.is_directory:
            if dest_str not in self.state["files"]:
                self.state["files"][dest_str] = {
                    "created": datetime.now().isoformat(),
                    "modifications": [],
                }

            self.state["files"][dest_str]["modifications"].append(
                {
                    "type": "moved",
                    "from": src_str,
                    "to": dest_str,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Keep only last 10 modifications
            if len(self.state["files"][dest_str]["modifications"]) > 10:
                self.state["files"][dest_str]["modifications"] = self.state["files"][dest_str]["modifications"][-10:]

            self._save_state()

        if self.on_change:
            # Pass both paths as a tuple for moves
            with contextlib.suppress(Exception):
                self.on_change("moved", (src_str, dest_str))

    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path
        if not event.is_directory:
            self._track_change("deleted", src_path)
        else:
            if self.on_change and not self._should_ignore(src_path):
                with contextlib.suppress(Exception):
                    self.on_change("deleted", src_path)

    def get_recent_changes(self, hours: int = 24) -> dict[str, dict]:
        """
        Get files changed in the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            Dict of {file_path: file_info} for recently changed files
        """
        cutoff = datetime.now().timestamp() - (hours * 3600)
        recent = {}

        for path, info in self.state["files"].items():
            if info["modifications"]:
                last_mod = datetime.fromisoformat(info["modifications"][-1]["timestamp"])
                if last_mod.timestamp() > cutoff:
                    recent[path] = info

        return recent


def start_monitoring(
    directories: list[Path],
    state_file: Path,
    monitor_config: Any,  # MonitorConfig from wks.api.monitor
    on_change: Callable[[str, str | tuple[str, str]], None] | None = None,
) -> Any:  # Observer type from watchdog
    """
    Start monitoring directories for changes.

    Args:
        directories: List of directories to monitor
        state_file: Path to state tracking file
        monitor_config: MonitorConfig instance for path filtering
        on_change: Optional callback for changes

    Returns:
        Observer instance (call .stop() to stop monitoring)
    """
    event_handler = WKSFileMonitor(
        state_file=state_file,
        monitor_config=monitor_config,
        on_change=on_change,
    )
    # Try observers in order of preference with fallback on start failures
    candidates: list[type] = []
    if FSEventsObserver is not None:
        candidates.append(FSEventsObserver)  # type: ignore
    if KqueueObserver is not None:
        candidates.append(KqueueObserver)  # type: ignore
    # Always include generic polling as last resort
    if PollingObserver is not None:
        candidates.append(PollingObserver)  # type: ignore
    # Default to base Observer if none of the above
    if not candidates:
        candidates = [Observer]  # type: ignore

    # Track last error encountered by the observer thread
    last_error: Exception | None = None
    for observer_class in candidates:
        try:
            observer = observer_class()  # type: ignore
            for directory in directories:
                observer.schedule(event_handler, str(directory), recursive=True)
            observer.start()
            return observer
        except Exception as e:  # pragma: no cover
            last_error = e
            with contextlib.suppress(Exception):
                observer.stop()
            continue
    # If we get here, all observers failed
    raise RuntimeError(f"Failed to start file observer: {last_error}")


if __name__ == "__main__":
    # Example usage
    from rich.console import Console

    console = Console()

    def on_file_change(event_type: str, path_info: str | tuple[str, str]) -> None:
        if isinstance(path_info, tuple):
            console.print(f"[yellow]{event_type}[/yellow]: {path_info[0]} -> {path_info[1]}")
        else:
            console.print(f"[yellow]{event_type}[/yellow]: {path_info}")

    # Monitor home directory
    from .api.monitor._FilterConfig import _FilterConfig
    from .api.monitor._PriorityConfig import _PriorityConfig
    from .api.monitor._SyncConfig import _SyncConfig
    from .api.monitor.MonitorConfig import MonitorConfig

    monitor_config = MonitorConfig(
        filter=_FilterConfig(
            include_paths=[],
            exclude_paths=[],
            include_dirnames=[],
            exclude_dirnames=[],
            include_globs=[],
            exclude_globs=[],
        ),
        database="monitor",
        priority=_PriorityConfig(dirs={}, weights={}),
        sync=_SyncConfig(max_documents=1000000, min_priority=0.0, prune_interval_secs=300.0),
    )
    observer = start_monitoring(
        directories=[Path.home()],
        state_file=Path.home() / WKS_HOME_EXT / "monitor_state.json",
        monitor_config=monitor_config,
        on_change=on_file_change,
    )

    try:
        console.print("[green]Monitoring started. Press Ctrl+C to stop.[/green]")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if observer is not None:
            observer.stop()
        console.print("[red]Monitoring stopped.[/red]")

    if observer is not None:
        observer.join()
