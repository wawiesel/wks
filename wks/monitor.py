"""
File system monitoring for WKS using watchdog.
Monitors directories and tracks file changes without external dependencies.
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class WKSFileMonitor(FileSystemEventHandler):
    """
    Monitor file system changes and track them for WKS.

    This replaces the A_GIS MongoDB-based monitoring with a simpler
    JSON-based tracking system suitable for personal use.
    """

    def __init__(
        self,
        state_file: Path,
        on_change: Optional[Callable[[str, str], None]] = None,
        ignore_patterns: Set[str] = None
    ):
        """
        Initialize the file monitor.

        Args:
            state_file: Path to JSON file for tracking state
            on_change: Callback function(event_type, file_path) when files change
            ignore_patterns: Set of patterns to ignore (e.g., {'.git', 'venv'})
        """
        super().__init__()
        self.state_file = Path(state_file)
        self.on_change = on_change
        self.ignore_patterns = ignore_patterns or {'.git', '__pycache__', '.DS_Store', 'venv', '.venv'}
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                # State file corrupted, back it up and start fresh
                backup_file = self.state_file.with_suffix('.json.backup')
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
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored based on patterns."""
        path_obj = Path(path)
        for pattern in self.ignore_patterns:
            if pattern in path_obj.parts:
                return True
            if path_obj.name.startswith('.'):
                return True
        return False

    def _track_change(self, event_type: str, path: str):
        """Track a file change in state."""
        if self._should_ignore(path):
            return

        path_str = str(Path(path).resolve())

        if path_str not in self.state["files"]:
            self.state["files"][path_str] = {
                "created": datetime.now().isoformat(),
                "modifications": []
            }

        self.state["files"][path_str]["modifications"].append({
            "type": event_type,
            "timestamp": datetime.now().isoformat()
        })

        # Keep only last 10 modifications per file
        if len(self.state["files"][path_str]["modifications"]) > 10:
            self.state["files"][path_str]["modifications"] = \
                self.state["files"][path_str]["modifications"][-10:]

        self._save_state()

        if self.on_change:
            self.on_change(event_type, path_str)

    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation."""
        if not event.is_directory:
            self._track_change("created", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        if not event.is_directory:
            self._track_change("modified", event.src_path)

    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move."""
        if not event.is_directory:
            # Track the move with both paths
            if self._should_ignore(event.src_path) or self._should_ignore(event.dest_path):
                return

            src_str = str(Path(event.src_path).resolve())
            dest_str = str(Path(event.dest_path).resolve())

            # Track move event
            if dest_str not in self.state["files"]:
                self.state["files"][dest_str] = {
                    "created": datetime.now().isoformat(),
                    "modifications": []
                }

            self.state["files"][dest_str]["modifications"].append({
                "type": "moved",
                "from": src_str,
                "to": dest_str,
                "timestamp": datetime.now().isoformat()
            })

            # Keep only last 10 modifications
            if len(self.state["files"][dest_str]["modifications"]) > 10:
                self.state["files"][dest_str]["modifications"] = \
                    self.state["files"][dest_str]["modifications"][-10:]

            self._save_state()

            if self.on_change:
                # Pass both paths as a tuple for moves
                self.on_change("moved", (src_str, dest_str))

    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        if not event.is_directory:
            self._track_change("deleted", event.src_path)

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
    on_change: Optional[Callable] = None
) -> Observer:
    """
    Start monitoring directories for changes.

    Args:
        directories: List of directories to monitor
        state_file: Path to state tracking file
        on_change: Optional callback for changes

    Returns:
        Observer instance (call .stop() to stop monitoring)
    """
    event_handler = WKSFileMonitor(state_file=state_file, on_change=on_change)
    observer = Observer()

    for directory in directories:
        observer.schedule(event_handler, str(directory), recursive=True)

    observer.start()
    return observer


if __name__ == "__main__":
    # Example usage
    from rich.console import Console

    console = Console()

    def on_file_change(event_type: str, path: str):
        console.print(f"[yellow]{event_type}[/yellow]: {path}")

    # Monitor home directory
    observer = start_monitoring(
        directories=[Path.home()],
        state_file=Path.home() / ".wks" / "monitor_state.json",
        on_change=on_file_change
    )

    try:
        console.print("[green]Monitoring started. Press Ctrl+C to stop.[/green]")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("[red]Monitoring stopped.[/red]")

    observer.join()
