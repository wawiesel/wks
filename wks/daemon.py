"""
WKS daemon for monitoring file system and updating Obsidian.

Adds support for ~/.wks/config.json with include/exclude path control.
"""

from .uri_utils import uri_to_path
from .priority import calculate_priority
from .utils import get_package_version, expand_path, file_checksum
from .config import load_config
from .config_validator import validate_and_raise, ConfigValidationError
from .dbmeta import resolve_db_compatibility, IncompatibleDatabase
from .mongoctl import MongoGuard, ensure_mongo_running
from .obsidian import ObsidianVault
from .monitor import start_monitoring
from .constants import WKS_HOME_EXT, WKS_DOT_DIRS, WKS_HOME_DISPLAY
from pymongo.collection import Collection
from typing import Optional, Set, List, Dict, Any
from pathlib import Path
import logging
import time
import json
import os
import threading
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)
try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover
    fcntl = None


try:
    from .config import mongo_settings
    from .similarity import build_similarity_from_config
    from .status import load_db_activity_summary, load_db_activity_history
except Exception:
    build_similarity_from_config = None  # type: ignore

    def load_db_activity_summary():  # type: ignore
        return {}

    def load_db_activity_history(max_age_secs: Optional[int] = None):  # type: ignore
        return []


class WKSDaemon:
    """Daemon that monitors filesystem and updates Obsidian vault."""

    def __init__(
        self,
        config: Dict[str, Any],
        vault_path: Path,
        base_dir: str,
        obsidian_log_max_entries: int,
        obsidian_active_files_max_rows: int,
        obsidian_source_max_chars: int,
        obsidian_destination_max_chars: int,
        obsidian_docs_keep: int,
        monitor_paths: list[Path],
        auto_project_notes: bool = False,
        ignore_dirnames: Optional[Set[str]] = None,
        exclude_paths: Optional[List[Path]] = None,
        ignore_patterns: Optional[Set[str]] = None,
        ignore_globs: Optional[List[str]] = None,
        similarity_db=None,
        similarity_extensions: Optional[Set[str]] = None,
        similarity_min_chars: int = 10,
        fs_rate_short_window_secs: float = 10.0,
        fs_rate_long_window_secs: float = 600.0,
        fs_rate_short_weight: float = 0.8,
        fs_rate_long_weight: float = 0.2,
        maintenance_interval_secs: float = 600.0,
        mongo_uri: Optional[str] = None,
        monitor_collection: Optional[Collection] = None,
    ):
        """
        Initialize WKS daemon.

        Args:
            vault_path: Path to Obsidian vault
            monitor_paths: List of paths to monitor
        """
        self.config = config
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
        # state_file removed - not needed
        self.ignore_dirnames = ignore_dirnames or set()
        self.exclude_paths = [Path(p).expanduser() for p in (exclude_paths or [])]
        self.ignore_patterns = ignore_patterns or set()
        self.observer = None
        self.auto_project_notes = bool(auto_project_notes)
        self.ignore_globs = ignore_globs or []
        # Single-instance lock
        self.lock_file = Path.home() / WKS_HOME_EXT / "daemon.lock"
        self._lock_fh = None
        # Similarity settings
        self.similarity = similarity_db
        self.similarity_extensions = {e.lower() for e in (similarity_extensions or set())}
        self.similarity_min_chars = int(similarity_min_chars)
        # Maintenance (periodic tasks)
        self._last_prune_check = 0.0
        # Read prune interval from config, default to 5 minutes (300 seconds)
        monitor_cfg = config.get("monitor", {})
        self._prune_interval_secs = float(monitor_cfg.get("prune_interval_secs", 300.0))
        # Coalesce delete events to avoid temp-file save false positives
        self._pending_deletes: Dict[str, float] = {}
        self._delete_grace_secs = 2.0
        # Coalesce modify/create bursts
        self._pending_mods: Dict[str, Dict[str, Any]] = {}
        self._mod_coalesce_secs = 0.6
        # Health
        self.health_file = Path.home() / WKS_HOME_EXT / "health.json"
        self._last_error = None
        self._last_error_at = None
        self._health_started_at = time.time()
        self._beat_count = 0
        # FS operation rate tracking
        self.fs_rate_short_window = max(float(fs_rate_short_window_secs), 1.0)
        self.fs_rate_long_window = max(float(fs_rate_long_window_secs), self.fs_rate_short_window)
        self.fs_rate_short_weight = float(fs_rate_short_weight)
        self.fs_rate_long_weight = float(fs_rate_long_weight)
        self._fs_events_short: deque[float] = deque()
        self._fs_events_long: deque[float] = deque()
        # Background maintenance (similarity DB audits)
        self._maintenance_interval_secs = max(float(maintenance_interval_secs), 1.0)
        self._maintenance_thread: Optional[threading.Thread] = None
        self._maintenance_stop_event = threading.Event()
        self.mongo_uri = str(mongo_uri or "")
        self._mongo_guard: Optional[MongoGuard] = None
        self.monitor_collection = monitor_collection

    @staticmethod
    def _get_touch_weight(raw_weight: Any) -> float:
        min_weight = 0.001
        max_weight = 1.0

        if raw_weight is None:
            raise ValueError("monitor.touch_weight missing")

        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid monitor.touch_weight {raw_weight!r}")

        if weight < min_weight:
            logger.warning("monitor.touch_weight %.6f below %.3f; using %.3f", weight, min_weight, min_weight)
            return min_weight

        if weight > max_weight:
            logger.warning("monitor.touch_weight %.6f above %.3f; using %.3f", weight, max_weight, max_weight)
            return max_weight

        return weight

    def _compute_touches_per_day(self, doc: Optional[Dict[str, Any]], now: datetime, weight: float) -> float:
        if not doc:
            return 0.0

        timestamp = doc.get("timestamp")
        if not isinstance(timestamp, str):
            return 0.0

        try:
            last_modified_time = datetime.fromisoformat(timestamp)
        except Exception:
            return 0.0

        dt = max((now - last_modified_time).total_seconds(), 0.0)
        prev_rate = doc.get("touches_per_day")

        if not isinstance(prev_rate, (int, float)) or prev_rate <= 0.0:
            interval = dt
        else:
            prev_interval = 1.0 / (prev_rate / 86400.0)
            interval = weight * dt + (1.0 - weight) * prev_interval

        if interval <= 0.0:
            return 0.0

        return 86400.0 / interval

    def _update_monitor_db(self, path: Path):
        if self.monitor_collection is None:
            return

        # Skip if file should be ignored
        if self._should_ignore_by_rules(path):
            return

        try:
            stat = path.stat()
            checksum = file_checksum(path)
            now = datetime.now()
            monitor_config = self.config.get("monitor", {})
            managed_dirs = monitor_config.get("managed_directories", {})
            priority_config = monitor_config.get("priority", {})

            try:
                touch_weight = self._get_touch_weight(monitor_config.get("touch_weight"))
            except ValueError as exc:
                self._set_error(f"monitor_config_error: {exc}")
                return
            priority = calculate_priority(path, managed_dirs, priority_config)

            path_uri = path.as_uri()
            existing_doc = self.monitor_collection.find_one(
                {"path": path_uri}, {"timestamp": 1, "touches_per_day": 1}
            )
            touches_per_day = self._compute_touches_per_day(existing_doc, now, touch_weight)

            doc = {
                "path": path_uri,
                "checksum": checksum,
                "bytes": stat.st_size,
                "priority": priority,
                "timestamp": now.isoformat(),
                "touches_per_day": touches_per_day,
            }

            self.monitor_collection.update_one({"path": doc["path"]}, {"$set": doc}, upsert=True)
            self._enforce_monitor_db_limit()
        except Exception as e:
            self._set_error(f"monitor_db_update_error: {e}")

    def _remove_from_monitor_db(self, path: Path):
        if self.monitor_collection is None:
            return
        try:
            self.monitor_collection.delete_one({"path": path.as_uri()})
        except Exception as e:
            self._set_error(f"monitor_db_delete_error: {e}")

    def _enforce_monitor_db_limit(self):
        if self.monitor_collection is None:
            return

        try:
            monitor_config = self.config.get("monitor", {})
            max_docs = monitor_config.get("max_documents", 1000000)

            count = self.monitor_collection.count_documents({})
            if count <= max_docs:
                return

            extras = count - max_docs
            if extras > 0:
                # Find and remove the lowest priority documents
                lowest_priority_docs = self.monitor_collection.find(
                    {}, {"_id": 1, "priority": 1}
                ).sort("priority", 1).limit(extras)

                ids_to_delete = [doc["_id"] for doc in lowest_priority_docs]
                if ids_to_delete:
                    self.monitor_collection.delete_many({"_id": {"$in": ids_to_delete}})
        except Exception as e:
            self._set_error(f"monitor_db_limit_error: {e}")

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

    def _record_fs_event(self, timestamp: Optional[float] = None) -> None:
        """Track raw file-system event timing for rate calculations."""
        t = timestamp or time.time()
        self._fs_events_short.append(t)
        self._fs_events_long.append(t)
        cutoff_short = t - self.fs_rate_short_window
        cutoff_long = t - self.fs_rate_long_window
        while self._fs_events_short and self._fs_events_short[0] < cutoff_short:
            self._fs_events_short.popleft()
        while self._fs_events_long and self._fs_events_long[0] < cutoff_long:
            self._fs_events_long.popleft()

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
        self._record_fs_event()
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

            # Update monitor DB (only if not ignored)
            if not self._should_ignore_by_rules(src):
                self._remove_from_monitor_db(src)
            if not self._should_ignore_by_rules(dest):
                self._update_monitor_db(dest)

            # Update similarity index
            try:
                if self.similarity:
                    # Robust handling for directory moves
                    if src.is_dir() and dest.is_dir() and hasattr(self.similarity, 'rename_folder'):
                        try:
                            self.similarity.rename_folder(src, dest)
                        except Exception:
                            pass
                    else:
                        # Prefer rename to preserve embedding and history
                        if hasattr(self.similarity, 'rename_file'):
                            ok = self.similarity.rename_file(src, dest)
                            if not ok:
                                # Fallback: re-add and remove old
                                if self._should_index_for_similarity(dest):
                                    self.similarity.add_file(dest)
                                self.similarity.remove_file(src)
                        else:
                            if self._should_index_for_similarity(dest):
                                self.similarity.add_file(dest)
                            self.similarity.remove_file(src)
            except Exception:
                pass
            return

        # Regular events
        path = Path(path_info)

        # Skip if file should be ignored
        if self._should_ignore_by_rules(path):
            return

        # Coalesce deletes: set pending and return; flush later
        if event_type == "deleted" and self._is_probably_file(path):
            try:
                self._pending_deletes[path.resolve().as_posix()] = time.time()
            except Exception:
                pass
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

    def start(self):
        """Start monitoring."""
        self._start_mongo_guard()
        # Acquire single-instance lock
        self._acquire_lock()
        self.vault.ensure_structure()

        self.observer = start_monitoring(
            directories=self.monitor_paths,
            state_file=Path.home() / WKS_HOME_EXT / "monitor_state.json",  # Temporary default
            on_change=self.on_file_change,
            ignore_dirs=self.ignore_dirnames,
            ignore_patterns=self.ignore_patterns,
            include_paths=self.monitor_paths,
            exclude_paths=self.exclude_paths,
            ignore_globs=self.ignore_globs,
        )

        print(f"WKS daemon started, monitoring: {[str(p) for p in self.monitor_paths]}")
        self._start_maintenance_thread()

    def stop(self):
        """Stop monitoring."""
        maintenance_stopped = self._stop_maintenance_thread()
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("WKS daemon stopped")
        if maintenance_stopped and self.similarity and hasattr(self.similarity, "close"):
            try:
                self.similarity.close()
            except Exception as exc:
                self._set_error(f"sim_close_error: {exc}")
            finally:
                self.similarity = None
        self._release_lock()
        self._stop_mongo_guard()

    def _start_mongo_guard(self):
        if not self.mongo_uri:
            return
        guard = self._mongo_guard
        if guard is None:
            guard = MongoGuard(self.mongo_uri, ping_interval=10.0)
            self._mongo_guard = guard
        guard.start(record_start=True)

    def _stop_mongo_guard(self):
        guard = self._mongo_guard
        if not guard:
            return
        try:
            guard.stop()
        except Exception:
            pass

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
                self._write_health()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    # -------------------------- Maintenance helpers -------------------------- #
    def _start_maintenance_thread(self):
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            return
        self._maintenance_stop_event.clear()
        thread = threading.Thread(
            target=self._maintenance_loop,
            name="wks-maintenance",
            daemon=True,
        )
        self._maintenance_thread = thread
        try:
            thread.start()
        except Exception:
            self._maintenance_thread = None

    def _stop_maintenance_thread(self) -> bool:
        thread = self._maintenance_thread
        if not thread:
            return True
        self._maintenance_stop_event.set()
        try:
            timeout = min(max(self._maintenance_interval_secs, 1.0) + 5.0, 60.0)
            thread.join(timeout=timeout)
        except Exception:
            pass
        if thread.is_alive():
            self._set_error("maintenance_stop_timeout")
            return False
        self._maintenance_thread = None
        self._maintenance_stop_event = threading.Event()
        return True

    def _maintenance_loop(self):
        interval = max(self._maintenance_interval_secs, 1.0)
        while not self._maintenance_stop_event.is_set():
            self._perform_similarity_maintenance()
            if self._maintenance_stop_event.wait(interval):
                break

    def _perform_similarity_maintenance(self):
        sim = self.similarity
        if not sim or not hasattr(sim, "audit_documents"):
            return
        try:
            summary = sim.audit_documents(remove_missing=True, fix_missing_metadata=True)
        except Exception as exc:
            error_msg = f"sim_audit_error: {exc.__class__.__name__}: {exc}"
            self._set_error(error_msg)
            logger.error("Similarity audit failed", exc_info=True, extra={"operation": "audit"})
            return
        if not isinstance(summary, dict):
            return
        try:
            removed = int(summary.get("removed", 0))
        except Exception:
            removed = summary.get("removed", 0) or 0
        try:
            updated = int(summary.get("updated", 0))
        except Exception:
            updated = summary.get("updated", 0) or 0
        if removed or updated:
            logger.info("Similarity maintenance completed", extra={
                "removed": removed,
                "updated": updated,
                "operation": "maintenance"
            })
            print(f"Similarity maintenance: removed {removed} entries, updated {updated} metadata")

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
        # Dotfile segments (including .wks/.wkso artefacts)
        for part in path.parts:
            if part in WKS_DOT_DIRS:
                return True
            if part.startswith('.'):
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

    def _maybe_prune_monitor_db(self):
        """Prune monitor database entries that are missing or match exclude rules."""
        if self.monitor_collection is None:
            return
        now = time.time()
        if now - self._last_prune_check < self._prune_interval_secs:
            return
        self._last_prune_check = now

        try:
            removed = 0
            # Iterate over all monitor entries
            cursor = self.monitor_collection.find({}, {"path": 1})
            for doc in cursor:
                uri = doc.get('path')
                if not uri:
                    continue

                # Convert URI to path for checking
                try:
                    p = uri_to_path(uri)
                except Exception:
                    continue

                # Check if file is missing
                try:
                    missing = not p.exists()
                except Exception:
                    missing = True

                # Check if file should be ignored by current rules
                ignored = False
                if not missing:
                    try:
                        ignored = self._should_ignore_by_rules(p)
                    except Exception:
                        ignored = False

                # Remove if missing or ignored
                if missing or ignored:
                    try:
                        self.monitor_collection.delete_one({"path": uri})
                        removed += 1
                    except Exception:
                        continue

            if removed:
                print(f"Monitor maintenance: pruned {removed} stale/excluded entries")
        except Exception as e:
            self._set_error(f"monitor_prune_error: {e}")

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

                self._remove_from_monitor_db(p)

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
                # Skip if file should be ignored
                if self._should_ignore_by_rules(p):
                    self._pending_mods.pop(pstr, None)
                    continue
                # Only log if still exists and is file
                if p.exists() and p.is_file():
                    try:
                        self.vault.log_file_operation(etype, p, tracked_files_count=self._get_tracked_files_count())
                        self._bump_beat()
                    except Exception as e:
                        self._set_error(f"ops_log_error: {e}")
                    self._update_monitor_db(p)

                    # Similarity indexing
                    try:
                        if self._should_index_for_similarity(p) and self.similarity:
                            updated = self.similarity.add_file(p)
                            if updated:
                                rec = self.similarity.get_last_add_result() or {}
                                ch = rec.get('content_checksum') or rec.get('content_hash')
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
            uptime_secs = int(now - self._health_started_at)

            db_summary = load_db_activity_summary()
            db_history_window = max(int(self.fs_rate_long_window), 600)
            db_history = load_db_activity_history(db_history_window)
            db_last_ts = None
            db_last_iso = None
            db_last_operation = None
            db_last_detail = None
            if db_summary:
                try:
                    db_last_ts = float(db_summary.get("timestamp"))
                except Exception:
                    db_last_ts = None
                db_last_iso = db_summary.get("timestamp_iso") or None
                db_last_operation = db_summary.get("operation") or None
                db_last_detail = db_summary.get("detail") or None

            if db_last_ts is None and db_history:
                try:
                    db_last_ts = float(db_history[-1].get("timestamp"))
                    db_last_iso = db_history[-1].get("timestamp_iso")
                    db_last_operation = db_history[-1].get("operation")
                    db_last_detail = db_history[-1].get("detail")
                except Exception:
                    pass

            cutoff_minute = now - 60.0
            db_ops_last_minute = 0
            for item in db_history:
                try:
                    ts_val = float(item.get("timestamp", 0))
                except Exception:
                    continue
                if ts_val >= cutoff_minute:
                    db_ops_last_minute += 1

            db_ops_per_min = round(db_ops_last_minute / 1.0, 2)
            self._beat_count = len(db_history)

            short_rate = len(self._fs_events_short) / self.fs_rate_short_window if self.fs_rate_short_window else 0.0
            long_rate = len(self._fs_events_long) / self.fs_rate_long_window if self.fs_rate_long_window else 0.0
            weighted_rate = (
                self.fs_rate_short_weight * short_rate
                + self.fs_rate_long_weight * long_rate
            )

            def _hms(secs: int) -> str:
                h = secs // 3600
                m = (secs % 3600) // 60
                s = secs % 60
                return f"{h:02d}:{m:02d}:{s:02d}"

            data = {
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
                "avg_beats_per_min": db_ops_per_min,
                # Lock status
                "lock_present": bool(self.lock_file.exists()),
                "lock_pid": (int(self.lock_file.read_text().strip().splitlines()[0]) if self.lock_file.exists() and self.lock_file.read_text().strip() else None) if True else None,
                "lock_path": str(self.lock_file),
                "db_last_operation": db_last_operation,
                "db_last_operation_detail": db_last_detail,
                "db_last_operation_iso": db_last_iso,
                "db_ops_last_minute": db_ops_last_minute,
                "fs_rate_short": short_rate,
                "fs_rate_long": long_rate,
                "fs_rate_weighted": weighted_rate,
                "fs_rate_short_window_secs": self.fs_rate_short_window,
                "fs_rate_long_window_secs": self.fs_rate_long_window,
                "fs_rate_short_weight": self.fs_rate_short_weight,
                "fs_rate_long_weight": self.fs_rate_long_weight,
            }
            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            with open(self.health_file, 'w') as f:
                _json.dump(data, f)
            # Update Health landing page
            try:
                self.vault.write_health_page()
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
        """Return number of unique files tracked in monitor DB."""
        if self.monitor_collection is not None:
            try:
                return self.monitor_collection.count_documents({})
            except Exception:
                return 0
        return 0


if __name__ == "__main__":
    import sys
    from pymongo import MongoClient

    # Load and validate config
    config = load_config()
    try:
        validate_and_raise(config)
    except ConfigValidationError as e:
        print(str(e))
        raise SystemExit(2)

    # Vault config (new structure)
    vault_cfg = config.get("vault", {})
    vault_path = expand_path(vault_cfg.get("base_dir", "~/obsidian"))
    base_dir = vault_cfg.get("wks_dir", "WKS")

    # Monitor config
    monitor_cfg = config.get("monitor", {})
    include_paths = [expand_path(p) for p in monitor_cfg.get("include_paths")]
    exclude_paths = [expand_path(p) for p in monitor_cfg.get("exclude_paths")]
    ignore_dirnames = set(monitor_cfg.get("ignore_dirnames"))
    ignore_patterns = set()  # deprecated
    ignore_globs = list(monitor_cfg.get("ignore_globs"))

    # DB config (new structure)
    db_cfg = config.get("db", {})
    mongo_uri = str(db_cfg.get("uri", "mongodb://localhost:27017/"))
    space_compat_tag, time_compat_tag = resolve_db_compatibility(config)
    ensure_mongo_running(mongo_uri, record_start=True)

    client = MongoClient(mongo_uri)
    monitor_db_name = monitor_cfg.get("database", "wks")
    monitor_coll_name = monitor_cfg.get("collection", "monitor")
    monitor_collection = client[monitor_db_name][monitor_coll_name]

    # Vault settings (backward compat: use old obsidian section if vault missing)
    obsidian_cfg = config.get("obsidian", {})
    if obsidian_cfg:
        # Legacy support
        obsidian_log_max_entries = int(obsidian_cfg.get("log_max_entries", 500))
        obsidian_active_files_max_rows = int(obsidian_cfg.get("active_files_max_rows", 50))
        obsidian_source_max_chars = int(obsidian_cfg.get("source_max_chars", 40))
        obsidian_destination_max_chars = int(obsidian_cfg.get("destination_max_chars", 40))
        obsidian_docs_keep = int(obsidian_cfg.get("docs_keep", 99))
        auto_project_notes = bool(obsidian_cfg.get("auto_project_notes", False))
    else:
        # New vault section defaults
        obsidian_log_max_entries = 500
        obsidian_active_files_max_rows = int(vault_cfg.get("activity_max_rows", 100))
        obsidian_source_max_chars = 40
        obsidian_destination_max_chars = 40
        obsidian_docs_keep = int(vault_cfg.get("max_extraction_docs", 50))
        auto_project_notes = False

    daemon = WKSDaemon(
        config=config,
        vault_path=vault_path,
        base_dir=base_dir,
        obsidian_log_max_entries=obsidian_log_max_entries,
        obsidian_active_files_max_rows=obsidian_active_files_max_rows,
        obsidian_source_max_chars=obsidian_source_max_chars,
        obsidian_destination_max_chars=obsidian_destination_max_chars,
        obsidian_docs_keep=obsidian_docs_keep,
        auto_project_notes=auto_project_notes,
        monitor_paths=include_paths,
        ignore_dirnames=ignore_dirnames,
        exclude_paths=exclude_paths,
        ignore_patterns=ignore_patterns,
        ignore_globs=ignore_globs,
        mongo_uri=mongo_uri,
        monitor_collection=monitor_collection,
    )

    # Similarity (explicit)
    sim_cfg_raw = config.get("similarity")
    if sim_cfg_raw and sim_cfg_raw.get("enabled"):
        if build_similarity_from_config is None:
            print("Fatal: similarity enabled but SimilarityDB not available")
            raise SystemExit(2)
        try:
            simdb, sim_cfg = build_similarity_from_config(
                config,
                require_enabled=True,
                compatibility_tag=space_compat_tag,
                product_version=get_package_version(),
            )
        except IncompatibleDatabase as exc:
            print(exc)
            raise SystemExit(2)
        except Exception as exc:
            print(f"Fatal: failed to initialize similarity DB: {exc}")
            raise SystemExit(2)
        if simdb is None or sim_cfg is None:
            print("Fatal: similarity initialization failed")
            raise SystemExit(2)
        daemon.similarity = simdb
        if bool(sim_cfg.get('offline', False)):
            import os as _os
            _os.environ.setdefault('HF_HUB_OFFLINE', '1')
            _os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
        daemon.similarity_extensions = set([e.lower() for e in sim_cfg["include_extensions"]])
        daemon.similarity_min_chars = int(sim_cfg["min_chars"])

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
