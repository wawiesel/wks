"""
File system monitoring for WKS using watchdog.
Monitors directories and tracks file changes without external dependencies.
"""

import time
import json
from pathlib import Path
import fnmatch
from datetime import datetime
from typing import Dict, Set, Callable, Optional, List, Iterable

from .constants import WKS_HOME_EXT, WKS_DOT_DIRS
from watchdog.observers import Observer
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
        ignore_patterns: Optional[Set[str]] = None,
        ignore_dirs: Optional[Set[str]] = None,
        include_paths: Optional[List[Path]] = None,
        exclude_paths: Optional[List[Path]] = None,
        ignore_globs: Optional[List[str]] = None,
        dot_whitelist: Optional[Iterable[str]] = None,
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
        # Deprecated: ignore_patterns. We'll fold these into glob rules for consistency.
        self.ignore_patterns = ignore_patterns or {'.git', '__pycache__', '.DS_Store', 'venv', '.venv', 'node_modules'}
        self.ignore_dirs = ignore_dirs or {'Library', 'Applications', '.Trash', '.cache', 'Cache', '_build'}
        # Paths to explicitly include/exclude (resolved)
        self.include_paths = [Path(p).expanduser().resolve() for p in include_paths] if include_paths else []
        self.exclude_paths = [Path(p).expanduser().resolve() for p in exclude_paths] if exclude_paths else []
        # Glob patterns (Unix shell-style) to ignore. Fold legacy ignore_patterns into globs.
        _globs = list(ignore_globs or [])
        if self.ignore_patterns:
            for tok in self.ignore_patterns:
                # Ignore a directory named tok anywhere, and files named tok
                _globs.append(f"**/{tok}/**")
                _globs.append(f"**/{tok}")
        self.ignore_globs = _globs
        # Dot-path whitelist that should never be ignored by default rules
        self._dot_whitelist = self._initialize_dot_whitelist(dot_whitelist)
        self.state = self._load_state()

    def _initialize_dot_whitelist(self, extra_whitelist: Optional[Iterable[str]]) -> Set[str]:
        """Build whitelist of dot-directories that should not be ignored."""
        whitelist: Set[str] = set()
        for entry in extra_whitelist or []:
            entry_str = str(entry).strip()
            if not entry_str:
                continue
            if entry_str in WKS_DOT_DIRS:
                # Always ignore WKS internal directories
                continue
            whitelist.add(entry_str)

        # Automatically whitelist dot-components that are explicitly included
        for include_path in self.include_paths:
            for part in include_path.parts:
                if part in WKS_DOT_DIRS:
                    continue
                if part.startswith('.'):
                    whitelist.add(part)
        return whitelist

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

    def _is_within(self, path: Path, base: Path) -> bool:
        """Return True if path is within base (or equal)."""
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored based on patterns."""
        path_obj = Path(path).resolve()

        # Exclude by explicit exclude paths
        for ex in self.exclude_paths:
            if self._is_within(path_obj, ex):
                return True

        # If include paths are provided, ignore anything outside them
        if self.include_paths:
            if not any(self._is_within(path_obj, inc) for inc in self.include_paths):
                return True

        # Check if any parent directory should be ignored
        for part in path_obj.parts:
            if part in self.ignore_dirs:
                return True
            # Ignore dot-directories except whitelisted
            if part in WKS_DOT_DIRS:
                return True
            if part.startswith('.') and part not in self._dot_whitelist:
                return True
            # Ignore directories starting with underscore (e.g., _build, _site)
            if part.startswith('_'):
                return True

        # No separate ignore_patterns check: patterns are folded into glob rules.

        # Glob-based ignores against full path and basename
        path_str = path_obj.as_posix()
        basename = path_obj.name
        for g in self.ignore_globs:
            try:
                if fnmatch.fnmatchcase(path_str, g) or fnmatch.fnmatchcase(basename, g):
                    # Preserve whitelist
                    if basename in self._dot_whitelist:
                        continue
                    return True
            except Exception:
                # Ignore malformed globs
                continue

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
    on_change: Optional[Callable] = None,
    ignore_dirs: Optional[Set[str]] = None,
    ignore_patterns: Optional[Set[str]] = None,
    include_paths: Optional[List[Path]] = None,
    exclude_paths: Optional[List[Path]] = None,
    ignore_globs: Optional[List[str]] = None,
    dot_whitelist: Optional[Iterable[str]] = None,
) -> Observer:
    """
    Start monitoring directories for changes.

    Args:
        directories: List of directories to monitor
        state_file: Path to state tracking file
        on_change: Optional callback for changes
        ignore_dirs: Optional set of directory names to ignore
        dot_whitelist: Optional iterable of dot-directory names to allow even if they start with '.'

    Returns:
        Observer instance (call .stop() to stop monitoring)
    """
    event_handler = WKSFileMonitor(
        state_file=state_file,
        on_change=on_change,
        ignore_dirs=ignore_dirs,
        ignore_patterns=ignore_patterns,
        include_paths=include_paths or directories,
        exclude_paths=exclude_paths,
        ignore_globs=ignore_globs,
        dot_whitelist=dot_whitelist,
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
