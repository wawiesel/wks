"""
File system monitoring for WKS using watchdog.
Monitors directories and tracks file changes without external dependencies.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from watchdog.observers import Observer

from .constants import WKS_HOME_EXT
from .monitor_rules import MonitorRules

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
        monitor_rules: MonitorRules,
        on_change: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize the file monitor.

        Args:
            state_file: Path to JSON file for tracking state
            on_change: Callback function(event_type, file_path) when files change
            ignore_patterns: Set of patterns to ignore (e.g., {'.git', 'venv'})
            ignore_dirs: Set of directory names to completely ignore
            dot_whitelist: Iterable of dot-directory names that should never be ignored
        """
        super().__init__()
        self.state_file = Path(state_file)
        self.on_change = on_change
        self.monitor_rules = monitor_rules
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
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
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored based on monitor rules."""
        try:
            return not self.monitor_rules.allows(Path(path))
        except Exception:
            return False

    def _track_change(self, event_type: str, path: str):
        """Track a file change in state."""
        if self._should_ignore(path):
            return

        path_str = str(Path(path).resolve())

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
        if not event.is_directory:
            self._track_change("created", event.src_path)
        else:
            # Emit callback for directory creation so higher layers can react (e.g., project notes)
            if self.on_change and not self._should_ignore(event.src_path):
                try:
                    self.on_change("created", event.src_path)
                except Exception:
                    pass

    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        if not event.is_directory:
            self._track_change("modified", event.src_path)

    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move."""
        # Track the move with both paths for files; emit callback for all
        if self._should_ignore(event.src_path) or self._should_ignore(event.dest_path):
            return

        src_str = str(Path(event.src_path).resolve())
        dest_str = str(Path(event.dest_path).resolve())

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
            try:
                self.on_change("moved", (src_str, dest_str))
            except Exception:
                pass

    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        if not event.is_directory:
            self._track_change("deleted", event.src_path)
        else:
            if self.on_change and not self._should_ignore(event.src_path):
                try:
                    self.on_change("deleted", event.src_path)
                except Exception:
                    pass

    def get_recent_changes(self, hours: int = 24) -> Dict[str, Dict]:
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
    monitor_rules: MonitorRules,
    on_change: Optional[Callable] = None,
) -> Observer:
    """
    Start monitoring directories for changes.

    Args:
        directories: List of directories to monitor
        state_file: Path to state tracking file
        on_change: Optional callback for changes
        monitor_rules: Shared include/exclude evaluation helper

    Returns:
        Observer instance (call .stop() to stop monitoring)
    """
    event_handler = WKSFileMonitor(
        state_file=state_file,
        monitor_rules=monitor_rules,
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
    last_error: Optional[Exception] = None
    for Obs in candidates:
        try:
            observer = Obs()  # type: ignore
            for directory in directories:
                observer.schedule(event_handler, str(directory), recursive=True)
            observer.start()
            return observer
        except Exception as e:  # pragma: no cover
            last_error = e
            try:
                observer.stop()
            except Exception:
                pass
            continue
    # If we get here, all observers failed
    raise RuntimeError(f"Failed to start file observer: {last_error}")


if __name__ == "__main__":
    # Example usage
    from rich.console import Console

    console = Console()

    def on_file_change(event_type: str, path: str):
        console.print(f"[yellow]{event_type}[/yellow]: {path}")

    # Monitor home directory
    observer = start_monitoring(
        directories=[Path.home()],
        state_file=Path.home() / WKS_HOME_EXT / "monitor_state.json",
        on_change=on_file_change,
    )

    try:
        console.print("[green]Monitoring started. Press Ctrl+C to stop.[/green]")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("[red]Monitoring stopped.[/red]")

    observer.join()
