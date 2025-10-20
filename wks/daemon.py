"""
WKS daemon for monitoring file system and updating Obsidian.

Adds support for ~/.wks/config.json with include/exclude path control.
"""

import time
import json
import os
try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover
    fcntl = None
from datetime import date
from pathlib import Path
from typing import Optional, Set, List, Dict, Any
from .monitor import start_monitoring
from .obsidian import ObsidianVault
from .activity import ActivityTracker
try:
    from .similarity import SimilarityDB
except Exception:
    SimilarityDB = None  # Optional dependency


class WKSDaemon:
    """Daemon that monitors filesystem and updates Obsidian vault."""

    def __init__(
        self,
        vault_path: Path,
        base_dir: str,
        obsidian_log_max_entries: int,
        obsidian_active_files_max_rows: int,
        obsidian_source_max_chars: int,
        obsidian_destination_max_chars: int,
        monitor_paths: list[Path],
        state_file: Optional[Path] = None,
        ignore_dirnames: Optional[Set[str]] = None,
        exclude_paths: Optional[List[Path]] = None,
        ignore_patterns: Optional[Set[str]] = None,
        ignore_globs: Optional[List[str]] = None,
        similarity_db=None,
        similarity_extensions: Optional[Set[str]] = None,
        similarity_min_chars: int = 10,
    ):
        """
        Initialize WKS daemon.

        Args:
            vault_path: Path to Obsidian vault
            monitor_paths: List of paths to monitor
            state_file: Path to monitoring state file
        """
        self.vault = ObsidianVault(
            vault_path,
            base_dir=base_dir,
            log_max_entries=obsidian_log_max_entries,
            active_files_max_rows=obsidian_active_files_max_rows,
            source_max_chars=obsidian_source_max_chars,
            destination_max_chars=obsidian_destination_max_chars,
        )
        self.monitor_paths = monitor_paths
        self.state_file = state_file or Path.home() / ".wks" / "monitor_state.json"
        self.ignore_dirnames = ignore_dirnames or set()
        self.exclude_paths = [Path(p).expanduser() for p in (exclude_paths or [])]
        self.ignore_patterns = ignore_patterns or set()
        self.observer = None
        # Activity tracking for ActiveFiles.md
        self.activity = ActivityTracker(Path.home() / ".wks" / "activity_state.json")
        self._last_active_update = 0.0
        self.ignore_globs = ignore_globs or []
        # Single-instance lock
        self.lock_file = Path.home() / ".wks" / "daemon.lock"
        self._lock_fh = None
        # Similarity settings
        self.similarity = similarity_db
        self.similarity_extensions = {e.lower() for e in (similarity_extensions or set())}
        self.similarity_min_chars = int(similarity_min_chars)

    def _should_index_for_similarity(self, path: Path) -> bool:
        if not self.similarity or not path.exists() or not path.is_file():
            return False
        if self.similarity_extensions:
            if path.suffix.lower() not in self.similarity_extensions:
                return False
        try:
            if path.stat().st_size < max(self.similarity_min_chars, 1):
                return False
        except Exception:
            return False
        return True

    def on_file_change(self, event_type: str, path_info):
        """
        Callback when a file changes.

        Args:
            event_type: Type of event (created, modified, moved, deleted)
            path_info: Path string for most events, or (src, dest) tuple for moves
        """
        # Handle move events specially
        if event_type == "moved":
            src_path, dest_path = path_info
            src = Path(src_path)
            dest = Path(dest_path)
            self.vault.log_file_operation("moved", src, dest, tracked_files_count=self._get_tracked_files_count())
            # Update symlink target if tracked
            try:
                self.vault.update_link_on_move(src, dest)
            except Exception:
                pass
            # Update similarity index
            try:
                if self.similarity:
                    # Prefer rename to preserve embedding
                    if hasattr(self.similarity, 'rename_file'):
                        self.similarity.rename_file(src, dest)
                    else:
                        # Fallback: re-add and remove old
                        if self._should_index_for_similarity(dest):
                            self.similarity.add_file(dest)
                        self.similarity.remove_file(src)
            except Exception:
                pass
            # Record activity on destination file
            try:
                self.activity.record_event(dest, event_type="moved")
            except Exception:
                pass
            self._maybe_update_active_files()
            return

        # Regular events
        path = Path(path_info)

        # Log to Obsidian
        if event_type in ["created", "modified", "deleted"]:
            self.vault.log_file_operation(event_type, path, tracked_files_count=self._get_tracked_files_count())
            # Track activity for created/modified (files only)
            if event_type in ["created", "modified"] and path.exists() and path.is_file():
                try:
                    self.activity.record_event(path, event_type=event_type)
                except Exception:
                    pass
                self._maybe_update_active_files()
                # Similarity indexing
                try:
                    if self._should_index_for_similarity(path):
                        self.similarity.add_file(path)
                except Exception:
                    pass
            elif event_type == "deleted":
                try:
                    if self.similarity:
                        self.similarity.remove_file(path)
                except Exception:
                    pass

        # Handle specific cases for non-move events
        if event_type == "created" and path_info and Path(path_info).is_dir():
            # New directory - check if it's a project
            p = Path(path_info)
            if p.parent == Path.home() and p.name.startswith("20"):
                # Looks like a project folder (YYYY-Name pattern)
                try:
                    self.vault.create_project_note(p, status="New")
                    self.vault.log_file_operation(
                        "created",
                        p,
                        details="Auto-created project note in Obsidian",
                        tracked_files_count=self._get_tracked_files_count(),
                    )
                except Exception as e:
                    print(f"Error creating project note: {e}")

    def _maybe_update_active_files(self, interval_seconds: float = 30.0):
        """Update ActiveFiles.md at most every interval_seconds."""
        now = time.time()
        if now - self._last_active_update < interval_seconds:
            return
        self._last_active_update = now
        try:
            # Use vault-configured max rows as the retrieval limit
            limit = getattr(self.vault, 'active_files_max_rows', 50)
            top = self.activity.get_top_active_files(limit=limit)
            self.vault.update_active_files(top)
        except Exception:
            pass

    def start(self):
        """Start monitoring."""
        # Acquire single-instance lock
        self._acquire_lock()
        self.vault.ensure_structure()

        self.observer = start_monitoring(
            directories=self.monitor_paths,
            state_file=self.state_file,
            on_change=self.on_file_change,
            ignore_dirs=self.ignore_dirnames,
            ignore_patterns=self.ignore_patterns,
            include_paths=self.monitor_paths,
            exclude_paths=self.exclude_paths,
            ignore_globs=self.ignore_globs,
        )

        print(f"WKS daemon started, monitoring: {[str(p) for p in self.monitor_paths]}")

    def stop(self):
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("WKS daemon stopped")
        self._release_lock()

    def run(self):
        """Run the daemon (blocking)."""
        try:
            self.start()
        except RuntimeError as e:
            print(str(e))
            return
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _acquire_lock(self):
        """Acquire an exclusive file lock to ensure a single daemon instance."""
        # Ensure directory exists
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        # If fcntl not available, fall back to a coarse PID file check
        if fcntl is None:
            if self.lock_file.exists():
                # Read PID and check if running
                try:
                    pid = int(self.lock_file.read_text().strip().splitlines()[0])
                except Exception:
                    pid = None
                if pid and pid > 0 and self._pid_running(pid):
                    raise RuntimeError(f"Another WKS daemon is already running (PID {pid}).")
            # Write current PID
            self.lock_file.write_text(str(os.getpid()))
            return
        # POSIX advisory lock
        try:
            self._lock_fh = open(self.lock_file, 'w')
            fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write PID and timestamp
            self._lock_fh.seek(0)
            self._lock_fh.truncate()
            self._lock_fh.write(f"{os.getpid()}\n")
            self._lock_fh.flush()
        except BlockingIOError:
            # Another process holds the lock
            raise RuntimeError("Another WKS daemon instance is already running.")
        except Exception as e:
            raise RuntimeError(f"Failed to acquire daemon lock: {e}")

    def _release_lock(self):
        """Release the single-instance lock."""
        try:
            if self._lock_fh and fcntl is not None:
                fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_UN)
                self._lock_fh.close()
                self._lock_fh = None
            # Best-effort cleanup
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def _pid_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _get_tracked_files_count(self) -> int:
        """Return number of unique files tracked in monitor state."""
        try:
            state_path = Path(self.state_file)
            if not state_path.exists():
                return 0
            data = json.load(open(state_path, 'r'))
            files = data.get('files') or {}
            return len(files)
        except Exception:
            return 0


if __name__ == "__main__":
    import sys

    def _expand(p: str) -> Path:
        return Path(p).expanduser()

    def _week_label() -> str:
        iso = date.today().isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def _add_week_suffix(p: Path) -> Path:
        s = str(p)
        if '{week}' in s:
            return Path(s.replace('{week}', _week_label())).expanduser()
        if '.' in p.name:
            stem = p.stem
            suffix = ''.join(p.suffixes)
            return p.with_name(f"{stem}-{_week_label()}{suffix}")
        else:
            return p.with_name(f"{p.name}-{_week_label()}")

    # Load config from ~/.wks/config.json
    config_path = Path.home() / ".wks" / "config.json"
    config: Dict[str, Any] = {}
    try:
        if config_path.exists():
            config = json.load(open(config_path, "r"))
    except Exception as e:
        print(f"Warning: failed to load config {config_path}: {e}")

    vault_path = _expand(config.get("vault_path", "~/obsidian"))

    monitor_cfg = config.get("monitor", {})

    include_paths = [
        _expand(p) for p in monitor_cfg.get("include_paths", [str(Path.home())])
    ]
    exclude_paths = [
        _expand(p) for p in monitor_cfg.get("exclude_paths", ["~/Library", "~/obsidian", "~/.wks"])
    ]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames", [
        'Applications', '.Trash', '.cache', 'Cache', 'Caches',
        'node_modules', 'venv', '.venv', '__pycache__', 'build', '_build', 'dist'
    ]))
    ignore_patterns = set(monitor_cfg.get("ignore_patterns", [
        '.git', '__pycache__', '.DS_Store', 'venv', '.venv', 'node_modules'
    ]))
    ignore_globs = list(monitor_cfg.get("ignore_globs", []))

    state_file = _expand(monitor_cfg.get("state_file", str(Path.home() / ".wks" / "monitor_state.json")))
    state_rollover = monitor_cfg.get("state_rollover", "weekly")  # weekly|none
    if state_rollover == "weekly":
        state_file = _add_week_suffix(state_file)

    # Activity tracker config
    activity_cfg = config.get("activity", {})
    activity_state_file = _expand(activity_cfg.get("state_file", str(Path.home() / ".wks" / "activity_state.json")))
    activity_rollover = activity_cfg.get("state_rollover", "weekly")
    if activity_rollover == "weekly":
        activity_state_file = _add_week_suffix(activity_state_file)

    daemon = WKSDaemon(
        vault_path=vault_path,
        monitor_paths=include_paths,
        state_file=state_file,
        ignore_dirnames=ignore_dirnames,
        exclude_paths=exclude_paths,
        ignore_patterns=ignore_patterns,
        ignore_globs=ignore_globs,
    )

    # Configure vault logging (weekly file logs)
    obsidian_cfg = config.get("obsidian", {})
    # Apply base_dir if provided so all files live under ~/obsidian/<base_dir>
    base_dir = obsidian_cfg.get("base_dir")
    if base_dir:
        try:
            daemon.vault.set_base_dir(base_dir)
        except Exception as e:
            print(f"Warning: failed to set Obsidian base_dir '{base_dir}': {e}")
    logs_cfg = obsidian_cfg.get("logs", {})
    weekly_logs = logs_cfg.get("weekly", False)
    logs_dirname = logs_cfg.get("dir", "Logs")
    max_entries = logs_cfg.get("max_entries", 500)
    active_cfg = obsidian_cfg.get("active", {})
    active_max_rows = active_cfg.get("max_rows", 50)
    # Optional path column widths
    source_max_chars = logs_cfg.get("source_max", 40)
    destination_max_chars = logs_cfg.get("destination_max", 40)
    daemon.vault.configure_logging(
        weekly_logs=weekly_logs,
        logs_dirname=logs_dirname,
        max_entries=max_entries,
        active_max_rows=active_max_rows,
        source_max_chars=source_max_chars,
        destination_max_chars=destination_max_chars,
    )

    # Recreate activity tracker with configured file (after daemon constructed)
    daemon.activity = ActivityTracker(activity_state_file)

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
