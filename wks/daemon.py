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
        obsidian_docs_keep: int,
        monitor_paths: list[Path],
        auto_project_notes: bool = False,
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
        self.docs_keep = int(obsidian_docs_keep)
        self.monitor_paths = monitor_paths
        self.state_file = state_file or Path.home() / ".wks" / "monitor_state.json"
        self.ignore_dirnames = ignore_dirnames or set()
        self.exclude_paths = [Path(p).expanduser() for p in (exclude_paths or [])]
        self.ignore_patterns = ignore_patterns or set()
        self.observer = None
        self.auto_project_notes = bool(auto_project_notes)
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
        # Maintenance (periodic tasks)
        self._last_prune_check = 0.0
        self._prune_interval_secs = 600.0  # run every 10 minutes
        # Coalesce delete events to avoid temp-file save false positives
        self._pending_deletes: Dict[str, float] = {}
        self._delete_grace_secs = 2.0
        # Coalesce modify/create bursts
        self._pending_mods: Dict[str, Dict[str, Any]] = {}
        self._mod_coalesce_secs = 0.6
        # Health
        self.health_file = Path.home() / ".wks" / "health.json"
        self._last_error = None
        self._last_error_at = None
        self._health_started_at = time.time()
        self._beat_count = 0

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

    def _is_probably_file(self, p: Path) -> bool:
        """Heuristic: log only file events; for deleted (nonexistent), use suffix-based guess."""
        try:
            if p.exists():
                return p.is_file()
        except Exception:
            pass
        name = p.name
        # Treat names with an extension as files (e.g., README.md); skip obvious directories
        return ('.' in name and not name.endswith('.') and name not in {'', '.', '..'})

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
            # Cancel any pending delete for destination (temp-file replace pattern)
            try:
                self._pending_deletes.pop(dest.resolve().as_posix(), None)
            except Exception:
                pass
            # Only log file moves; skip pure directory moves to reduce noise
            try:
                if self._is_probably_file(src) or self._is_probably_file(dest):
                    self.vault.log_file_operation("moved", src, dest, tracked_files_count=self._get_tracked_files_count())
                    self._bump_beat()
            except Exception:
                pass
            # Update symlink target if tracked
            try:
                self.vault.update_link_on_move(src, dest)
            except Exception:
                pass
            # Update wiki links inside vault
            try:
                self.vault.update_vault_links_on_move(src, dest)
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

        # Coalesce deletes: set pending and return; flush later
        if event_type == "deleted" and self._is_probably_file(path):
            try:
                self._pending_deletes[path.resolve().as_posix()] = time.time()
            except Exception:
                pass
            self._maybe_update_active_files()
            return

        # Created/modified: cancel any pending delete for same path and coalesce modify
        if event_type in ["created", "modified"]:
            try:
                self._pending_deletes.pop(path.resolve().as_posix(), None)
            except Exception:
                pass
            # Queue pending mod/create
            try:
                key = path.resolve().as_posix()
                rec = self._pending_mods.get(key) or {}
                rec["event_type"] = event_type
                rec["when"] = time.time()
                self._pending_mods[key] = rec
            except Exception:
                pass
            return

        # Handle specific cases for non-move events
        if event_type == "created" and path_info and Path(path_info).is_dir():
            # New directory - check if it's a project
            p = Path(path_info)
            if self.auto_project_notes and p.parent == Path.home() and p.name.startswith("20"):
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
            # Refresh angle snapshots so deg/min can be negative as files cool down
            try:
                self.activity.refresh_angles_all()
            except Exception:
                pass
            # Use vault-configured max rows as the retrieval limit
            limit = getattr(self.vault, 'active_files_max_rows', 50)
            top = self.activity.get_top_active_files(limit=limit)
            # Fallback: if no tracked activity yet (fresh state), backfill with recent files
            if not top:
                try:
                    import json as _json
                    ms_path = self.state_file or (Path.home()/'.wks'/'monitor_state.json')
                    recent = []
                    if ms_path and Path(ms_path).exists():
                        ms = _json.load(open(ms_path, 'r'))
                        files = (ms.get('files') or {})
                        for pstr, info in files.items():
                            mods = info.get('modifications') or []
                            if not mods:
                                continue
                            ts = mods[-1].get('timestamp')
                            if not ts:
                                continue
                            try:
                                from datetime import datetime as _dt
                                t = _dt.fromisoformat(ts)
                            except Exception:
                                continue
                            recent.append((pstr, t.timestamp()))
                        # Sort by most recent modification
                        recent.sort(key=lambda x: x[1], reverse=True)
                        # Map to (path, small_angle, delta)
                        small = 0.05
                        top = [(p, small, 0.0) for p, _ in recent[:limit]]
                except Exception:
                    pass
            # Fallback 2: use recent file operations ledger if still empty
            if not top:
                try:
                    ops_path = Path.home()/'.wks'/'file_ops.jsonl'
                    if ops_path.exists():
                        lines = ops_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                        # newest are at end; walk backwards and collect unique paths
                        seen = set()
                        picks = []
                        import json as _json
                        for line in reversed(lines[-200:]):
                            try:
                                rec = _json.loads(line)
                            except Exception:
                                continue
                            for key in ('destination','source'):
                                pstr = rec.get(key)
                                if not pstr:
                                    continue
                                if pstr in seen:
                                    continue
                                seen.add(pstr)
                                picks.append(pstr)
                                if len(picks) >= limit:
                                    break
                            if len(picks) >= limit:
                                break
                        small = 0.02
                        top = [(p, small, 0.0) for p in picks]
                except Exception:
                    pass
            # Provide tracker for deg/min and last modified
            self.vault.update_active_files(top, tracker=self.activity)
        except Exception:
            pass

    def start(self):
        """Start monitoring."""
        # Acquire single-instance lock
        self._acquire_lock()
        self.vault.ensure_structure()
        # Rebuild ActiveFiles immediately on start
        try:
            self._last_active_update = 0.0
            self._maybe_update_active_files(interval_seconds=0.0)
        except Exception:
            pass

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
                # Flush pending deletes and periodic maintenance
                self._maybe_flush_pending_deletes()
                self._maybe_flush_pending_mods()
                self._maybe_prune_similarity_db()
                # Ensure ActiveFiles refreshes even during quiet periods
                self._maybe_update_active_files()
                self._write_health()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    # -------------------------- Maintenance helpers -------------------------- #
    def _within_any(self, path: Path, bases: list[Path]) -> bool:
        for base in bases or []:
            try:
                path.resolve().relative_to(base.resolve())
                return True
            except Exception:
                continue
        return False

    def _should_ignore_by_rules(self, path: Path) -> bool:
        # Outside include paths
        if self.monitor_paths and not self._within_any(path, self.monitor_paths):
            return True
        # Inside exclude roots
        if any(self._within_any(path, [ex]) for ex in (self.exclude_paths or [])):
            return True
        # Dotfile segments (except .wks)
        for part in path.parts:
            if part.startswith('.') and part != '.wks':
                return True
        # Named ignored directories
        for part in path.parts:
            if part in (self.ignore_dirnames or set()):
                return True
        # Glob-based ignores (full path and basename)
        try:
            import fnmatch as _fn
            pstr = path.as_posix()
            for g in (self.ignore_globs or []):
                try:
                    if _fn.fnmatchcase(pstr, g) or _fn.fnmatchcase(path.name, g):
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _maybe_prune_similarity_db(self):
        if not self.similarity:
            return
        now = time.time()
        if now - self._last_prune_check < self._prune_interval_secs:
            return
        self._last_prune_check = now
        # Best-effort prune: remove docs for missing files or ignored paths
        try:
            removed = 0
            # Iterate lazily to avoid loading everything at once
            cursor = self.similarity.collection.find({}, {"path": 1})
            for doc in cursor:
                pstr = doc.get('path')
                if not pstr:
                    continue
                p = Path(pstr)
                try:
                    missing = not p.exists()
                except Exception:
                    missing = True
                ignored = False
                if not missing:
                    try:
                        ignored = self._should_ignore_by_rules(p)
                    except Exception:
                        ignored = False
                if missing or ignored:
                    try:
                        # Remove file-level
                        self.similarity.collection.delete_one({"path": pstr})
                        # Remove related chunks
                        try:
                            self.similarity.chunks.delete_many({"file_path": pstr})
                        except Exception:
                            pass
                        removed += 1
                    except Exception:
                        continue
            if removed:
                print(f"Similarity maintenance: pruned {removed} stale/ignored entries")
        except Exception as e:
            self._set_error(f"prune_error: {e}")
            # Never let maintenance crash the daemon
            pass

    def _maybe_flush_pending_deletes(self):
        """Log deletes after a short grace period to avoid temp-file saves showing as delete+recreate."""
        if not self._pending_deletes:
            return
        now = time.time()
        expired = []
        for pstr, ts in list(self._pending_deletes.items()):
            if now - ts >= self._delete_grace_secs:
                expired.append(pstr)
        for pstr in expired:
            try:
                p = Path(pstr)
                # If the path exists again, skip logging delete
                if p.exists():
                    self._pending_deletes.pop(pstr, None)
                    continue
                # Log deletion now
                try:
                    self.vault.log_file_operation("deleted", p, tracked_files_count=self._get_tracked_files_count())
                except Exception as e:
                    self._set_error(f"delete_log_error: {e}")
                    pass
                try:
                    if self.similarity:
                        self.similarity.remove_file(p)
                except Exception as e:
                    self._set_error(f"sim_remove_error: {e}")
                    pass
                try:
                    self.vault.mark_reference_deleted(p)
                except Exception as e:
                    self._set_error(f"mark_ref_error: {e}")
                    pass
                self._pending_deletes.pop(pstr, None)
            except Exception:
                # Best-effort
                try:
                    self._pending_deletes.pop(pstr, None)
                except Exception:
                    pass

    def _maybe_flush_pending_mods(self):
        if not self._pending_mods:
            return
        now = time.time()
        ready = []
        for pstr, rec in list(self._pending_mods.items()):
            if now - rec.get("when", 0) >= self._mod_coalesce_secs:
                ready.append((pstr, rec.get("event_type", "modified")))
        for pstr, etype in ready:
            try:
                p = Path(pstr)
                # Only log if still exists and is file
                if p.exists() and p.is_file():
                    try:
                        self.vault.log_file_operation(etype, p, tracked_files_count=self._get_tracked_files_count())
                        self._bump_beat()
                    except Exception as e:
                        self._set_error(f"ops_log_error: {e}")
                    try:
                        self.activity.record_event(p, event_type=etype)
                    except Exception as e:
                        self._set_error(f"activity_error: {e}")
                    self._maybe_update_active_files()
                    # Similarity indexing
                    try:
                        if self._should_index_for_similarity(p) and self.similarity:
                            updated = self.similarity.add_file(p)
                            if updated:
                                rec = self.similarity.get_last_add_result() or {}
                                ch = rec.get('content_hash')
                                txt = rec.get('text')
                                if ch and txt is not None:
                                    try:
                                        self.vault.write_doc_text(ch, p, txt, keep=self.docs_keep)
                                    except Exception as e:
                                        self._set_error(f"doc_write_error: {e}")
                    except Exception as e:
                        self._set_error(f"sim_add_error: {e}")
                self._pending_mods.pop(pstr, None)
            except Exception:
                try:
                    self._pending_mods.pop(pstr, None)
                except Exception:
                    pass

    def _write_health(self):
        try:
            now = time.time()
            # count this tick as a beat
            self._beat_count += 1
            uptime_secs = int(now - self._health_started_at)
            def _hms(secs:int):
                h = secs // 3600; m = (secs % 3600) // 60; s = secs % 60
                return f"{h:02d}:{m:02d}:{s:02d}"
            data = {
                "heartbeat": int(now),
                "heartbeat_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now)),
                "pending_deletes": len(self._pending_deletes),
                "pending_mods": len(self._pending_mods),
                "last_error": self._last_error,
                "pid": os.getpid(),
                "last_error_at": int(self._last_error_at) if self._last_error_at else None,
                "last_error_at_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._last_error_at)) if self._last_error_at else None,
                "last_error_age_secs": int(now - self._last_error_at) if self._last_error_at else None,
                "started_at": int(self._health_started_at),
                "started_at_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._health_started_at)),
                "uptime_secs": uptime_secs,
                "uptime_hms": _hms(uptime_secs),
                "beats": int(self._beat_count),
                "avg_beats_per_min": round(self._beat_count / max(1.0, (now - self._health_started_at) / 60.0), 2),
                # Lock status
                "lock_present": bool(self.lock_file.exists()),
                "lock_pid": (int(self.lock_file.read_text().strip().splitlines()[0]) if self.lock_file.exists() and self.lock_file.read_text().strip() else None) if True else None,
                "lock_path": str(self.lock_file),
            }
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            with open(self.health_file, 'w') as f:
                _json.dump(data, f)
            # Update Health landing page
            try:
                self.vault.write_health_page(state_file=self.state_file)
            except Exception:
                pass
        except Exception:
            pass

    def _bump_beat(self):
        try:
            self._beat_count += 1
        except Exception:
            pass

    def _set_error(self, msg: str):
        try:
            self._last_error = str(msg)
            self._last_error_at = time.time()
        except Exception:
            pass

    def _acquire_lock(self):
        """Acquire an exclusive file lock to ensure a single daemon instance."""
        # Ensure directory exists
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        # Stale lock auto-clean: if lock exists but PID is not running, remove it
        try:
            if self.lock_file.exists():
                try:
                    raw = self.lock_file.read_text().strip().splitlines()
                    stale_pid = int(raw[0]) if raw else None
                except Exception:
                    stale_pid = None
                if stale_pid and not self._pid_running(stale_pid):
                    try:
                        self.lock_file.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
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

    # Weekly log filename helpers removed (feature deprecated)

    # Load config from ~/.wks/config.json
    config_path = Path.home() / ".wks" / "config.json"
    config: Dict[str, Any] = {}
    try:
        if config_path.exists():
            config = json.load(open(config_path, "r"))
    except Exception as e:
        print(f"Warning: failed to load config {config_path}: {e}")

    # Require vault_path
    if "vault_path" not in config or not str(config.get("vault_path")).strip():
        print("Fatal: 'vault_path' is required in ~/.wks/config.json")
        raise SystemExit(2)
    vault_path = _expand(config.get("vault_path"))

    monitor_cfg = config.get("monitor", {})
    missing_mon = []
    for key in ["include_paths", "exclude_paths", "ignore_dirnames", "ignore_globs", "state_file"]:
        if key not in monitor_cfg:
            missing_mon.append(f"monitor.{key}")
    if missing_mon:
        print("Fatal: missing required config keys: " + ", ".join(missing_mon))
        raise SystemExit(2)

    include_paths = [_expand(p) for p in monitor_cfg.get("include_paths")]
    exclude_paths = [_expand(p) for p in monitor_cfg.get("exclude_paths")]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames"))
    ignore_patterns = set()  # deprecated
    ignore_globs = list(monitor_cfg.get("ignore_globs"))
    state_file = _expand(monitor_cfg.get("state_file"))

    # Activity tracker config (optional but recommended)
    activity_cfg = config.get("activity", {})
    activity_state_file = _expand(activity_cfg.get("state_file", str(Path.home() / ".wks" / "activity_state.json")))

    # Obsidian config (explicit)
    obsidian_cfg = config.get("obsidian", {})
    base_dir = obsidian_cfg.get("base_dir")
    required_obs = ["log_max_entries", "active_files_max_rows", "source_max_chars", "destination_max_chars"]
    missing_obs = [f"obsidian.{k}" for k in ["base_dir"] if not base_dir] + [f"obsidian.{k}" for k in required_obs if k not in obsidian_cfg]
    if missing_obs:
        print("Fatal: missing required config keys: " + ", ".join(missing_obs))
        raise SystemExit(2)

    daemon = WKSDaemon(
        vault_path=vault_path,
        base_dir=base_dir,
        obsidian_log_max_entries=int(obsidian_cfg["log_max_entries"]),
        obsidian_active_files_max_rows=int(obsidian_cfg["active_files_max_rows"]),
        obsidian_source_max_chars=int(obsidian_cfg["source_max_chars"]),
        obsidian_destination_max_chars=int(obsidian_cfg["destination_max_chars"]),
        obsidian_docs_keep=int(obsidian_cfg.get("docs_keep", 99)),
        auto_project_notes=bool(obsidian_cfg.get("auto_project_notes", False)),
        monitor_paths=include_paths,
        state_file=state_file,
        ignore_dirnames=ignore_dirnames,
        exclude_paths=exclude_paths,
        ignore_patterns=ignore_patterns,
        ignore_globs=ignore_globs,
    )

    # Recreate activity tracker with configured file (after daemon constructed)
    daemon.activity = ActivityTracker(activity_state_file)

    # Similarity (explicit)
    sim_cfg = config.get("similarity")
    if sim_cfg is None or "enabled" not in sim_cfg:
        print("Fatal: 'similarity.enabled' is required (true/false) in ~/.wks/config.json")
        raise SystemExit(2)
    if sim_cfg.get("enabled"):
        if SimilarityDB is None:
            print("Fatal: similarity enabled but SimilarityDB not available")
            raise SystemExit(2)
        required = ["mongo_uri", "database", "collection", "model", "include_extensions", "min_chars", "max_chars", "chunk_chars", "chunk_overlap"]
        missing = [k for k in required if k not in sim_cfg]
        if missing:
            print("Fatal: missing required similarity keys: " + ", ".join([f"similarity.{k}" for k in missing]))
            raise SystemExit(2)
        # Extraction config (explicit)
        extract_cfg = config.get("extract")
        if extract_cfg is None or 'engine' not in extract_cfg or 'ocr' not in extract_cfg or 'timeout_secs' not in extract_cfg:
            print("Fatal: 'extract.engine', 'extract.ocr', and 'extract.timeout_secs' are required in config")
            raise SystemExit(2)
        # Offline hint to avoid network
        if bool(sim_cfg.get('offline', False)):
            import os as _os
            _os.environ.setdefault('HF_HUB_OFFLINE', '1')
            _os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        from .similarity import SimilarityDB as _S
        daemon.similarity = _S(
            database_name=sim_cfg["database"],
            collection_name=sim_cfg["collection"],
            mongo_uri=sim_cfg["mongo_uri"],
            model_name=sim_cfg["model"],
            model_path=sim_cfg.get("model_path"),
            offline=bool(sim_cfg.get("offline", False)),
            max_chars=int(sim_cfg["max_chars"]),
            chunk_chars=int(sim_cfg["chunk_chars"]),
            chunk_overlap=int(sim_cfg["chunk_overlap"]),
            extract_engine=extract_cfg['engine'],
            extract_ocr=bool(extract_cfg['ocr']),
            extract_timeout_secs=int(extract_cfg['timeout_secs']),
        )
        daemon.similarity_extensions = set([e.lower() for e in sim_cfg["include_extensions"]])
        daemon.similarity_min_chars = int(sim_cfg["min_chars"])

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
