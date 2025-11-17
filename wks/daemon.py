"""
WKS daemon for monitoring file system and updating Obsidian.

Adds support for ~/.wks/config.json with include/exclude path control.
"""

from .uri_utils import uri_to_path
from .priority import calculate_priority
from .utils import get_package_version, expand_path, file_checksum
from .config import load_config
from .config_validator import validate_and_raise, ConfigValidationError
from .mongoctl import MongoGuard, ensure_mongo_running
from .mcp_bridge import MCPBroker
from .mcp_paths import mcp_socket_path
from .vault.obsidian import ObsidianVault
from .vault.indexer import VaultLinkIndexer
from .monitor import start_monitoring
from .constants import WKS_HOME_EXT, WKS_HOME_DISPLAY
from .monitor_rules import MonitorRules
from .monitor_controller import MonitorConfig
from pymongo.collection import Collection
from typing import Optional, Set, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict
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


@dataclass
class HealthData:
    """Health data structure for daemon health.json file."""
    pending_deletes: int
    pending_mods: int
    last_error: Optional[str]
    pid: int
    last_error_at: Optional[int]
    last_error_at_iso: Optional[str]
    last_error_age_secs: Optional[int]
    started_at: int
    started_at_iso: str
    uptime_secs: int
    uptime_hms: str
    beats: int
    avg_beats_per_min: float
    lock_present: bool
    lock_pid: Optional[int]
    lock_path: str
    db_last_operation: Optional[str]
    db_last_operation_detail: Optional[str]
    db_last_operation_iso: Optional[str]
    db_ops_last_minute: int
    fs_rate_short: float
    fs_rate_long: float
    fs_rate_weighted: float
    fs_rate_short_window_secs: float
    fs_rate_long_window_secs: float
    fs_rate_short_weight: float
    fs_rate_long_weight: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


try:
    from .config import mongo_settings
    from .status import load_db_activity_summary, load_db_activity_history
except Exception:
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
        monitor_rules: MonitorRules,
        auto_project_notes: bool = False,
        fs_rate_short_window_secs: float = 10.0,
        fs_rate_long_window_secs: float = 600.0,
        fs_rate_short_weight: float = 0.8,
        fs_rate_long_weight: float = 0.2,
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
        vault_cfg = config.get("vault", {})
        self._vault_indexer = VaultLinkIndexer.from_config(self.vault, config)
        self._vault_sync_interval = float(vault_cfg.get("update_frequency_seconds", 300.0))
        self._last_vault_sync = 0.0
        self.docs_keep = int(obsidian_docs_keep)
        self.monitor_paths = [Path(p).expanduser().resolve() for p in monitor_paths]
        self.monitor_rules = monitor_rules
        self.observer = None
        self.auto_project_notes = auto_project_notes
        # Single-instance lock
        self.lock_file = Path.home() / WKS_HOME_EXT / "daemon.lock"
        self._lock_fh = None
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
        self.mongo_uri = str(mongo_uri or "")
        self._mongo_guard: Optional[MongoGuard] = None
        self.monitor_collection = monitor_collection
        self._mcp_broker: Optional[MCPBroker] = None
        self._mcp_socket = mcp_socket_path()

    @staticmethod
    def _get_touch_weight(raw_weight: Any) -> float:
        min_weight = 0.001
        max_weight = 1.0

        if raw_weight is None:
            raise ValueError("monitor.touch_weight is required in config (found: missing, expected: float between 0.001 and 1.0)")

        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            raise ValueError(f"monitor.touch_weight must be a number between 0.001 and 1 (found: {type(raw_weight).__name__} = {raw_weight!r}, expected: float between 0.001 and 1.0)")

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

    def _monitor_has_path(self, path: Path) -> bool:
        """Check whether the monitor DB currently tracks the given path."""
        if self.monitor_collection is None:
            return False
        try:
            return self.monitor_collection.count_documents({"path": path.as_uri()}, limit=1) > 0
        except Exception as exc:
            self._set_error(f"monitor_db_lookup_error: {exc}")
            return False

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

    def _handle_move_event(self, src_path: str, dest_path: str):
        """Handle file move event."""
        src = Path(src_path)
        dest = Path(dest_path)

        # Cancel any pending delete for destination (temp-file replace pattern)
        try:
            self._pending_deletes.pop(dest.resolve().as_posix(), None)
        except Exception:
            pass

        tracked_src = self._monitor_has_path(src)
        dest_is_file = False
        try:
            dest_is_file = dest.exists() and dest.is_file()
        except Exception:
            dest_is_file = False

        if tracked_src or dest_is_file:
            try:
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
        if tracked_src and not self._should_ignore_by_rules(src):
            self._remove_from_monitor_db(src)
        if dest_is_file and not self._should_ignore_by_rules(dest):
            self._update_monitor_db(dest)

    def _handle_delete_event(self, path: Path):
        """Handle file delete event."""
        if not self._monitor_has_path(path):
            return
        try:
            self._pending_deletes[path.resolve().as_posix()] = time.time()
        except Exception:
            pass

    def _handle_create_modify_event(self, path: Path, event_type: str):
        """Handle file create or modify event."""
        # Cancel any pending delete for same path
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

    def _handle_new_directory(self, path: Path):
        """Handle new directory creation - check if it's a project."""
        if not self.auto_project_notes:
            return

        # Check if it looks like a project folder (YYYY-Name pattern)
        if path.parent == Path.home() and path.name.startswith("20"):
            try:
                self.vault.create_project_note(path, status="New")
                self.vault.log_file_operation(
                    "created",
                    path,
                    details="Auto-created project note in Obsidian",
                    tracked_files_count=self._get_tracked_files_count(),
                )
            except Exception as e:
                print(f"Error creating project note: {e}")

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
            self._handle_move_event(src_path, dest_path)
            return

        # Regular events
        path = Path(path_info)

        # Skip if file should be ignored
        if self._should_ignore_by_rules(path):
            return

        # Coalesce deletes: set pending and return; flush later
        if event_type == "deleted":
            self._handle_delete_event(path)
            return

        # Created/modified: cancel any pending delete for same path and coalesce modify
        if event_type in ["created", "modified"]:
            self._handle_create_modify_event(path, event_type)

            # Handle specific cases for new directories
            if event_type == "created" and path.is_dir():
                self._handle_new_directory(path)
            return

    def start(self):
        """Start monitoring."""
        self._start_mongo_guard()
        self._start_mcp_broker()
        # Acquire single-instance lock
        self._acquire_lock()
        self.vault.ensure_structure()

        self.observer = start_monitoring(
            directories=self.monitor_paths,
            state_file=Path.home() / WKS_HOME_EXT / "monitor_state.json",  # Temporary default
            monitor_rules=self.monitor_rules,
            on_change=self.on_file_change,
        )

        print(f"WKS daemon started, monitoring: {[str(p) for p in self.monitor_paths]}")

    def stop(self):
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            print("WKS daemon stopped")
        self._release_lock()
        self._stop_mongo_guard()
        self._stop_mcp_broker()

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

    def _start_mcp_broker(self):
        socket_path = self._mcp_socket
        if not socket_path:
            return
        broker = self._mcp_broker
        if broker is None:
            broker = MCPBroker(socket_path)
            self._mcp_broker = broker
        try:
            broker.start()
        except Exception as exc:
            self._set_error(f"mcp_broker_error: {exc}")

    def _stop_mcp_broker(self):
        broker = self._mcp_broker
        if not broker:
            return
        try:
            broker.stop()
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
                self._write_health()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _should_ignore_by_rules(self, path: Path) -> bool:
        try:
            return not self.monitor_rules.allows(path)
        except Exception:
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
                self._pending_mods.pop(pstr, None)
            except Exception:
                try:
                    self._pending_mods.pop(pstr, None)
                except Exception:
                    pass

    def _maybe_sync_vault_links(self):
        if not getattr(self, "_vault_indexer", None):
            return
        now = time.time()
        if now - getattr(self, "_last_vault_sync", 0.0) < self._vault_sync_interval:
            return
        try:
            self._vault_indexer.sync()
        except Exception as exc:
            self._set_error(f"vault_sync_error: {exc}")
        finally:
            self._last_vault_sync = now

    def _get_db_activity_info(self, now: float) -> tuple[Optional[str], Optional[str], Optional[str], int]:
        """Get DB activity information from summary and history.

        Returns:
            Tuple of (last_operation, last_detail, last_iso, ops_last_minute)
        """
        db_summary = load_db_activity_summary()
        db_history_window = max(int(self.fs_rate_long_window), 600)
        db_history = load_db_activity_history(db_history_window)

        db_last_operation = None
        db_last_detail = None
        db_last_iso = None

        if db_summary:
            try:
                db_last_iso = db_summary.get("timestamp_iso") or None
                db_last_operation = db_summary.get("operation") or None
                db_last_detail = db_summary.get("detail") or None
            except Exception:
                pass

        if db_last_operation is None and db_history:
            try:
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

        self._beat_count = len(db_history)
        return db_last_operation, db_last_detail, db_last_iso, db_ops_last_minute

    def _calculate_fs_rates(self) -> tuple[float, float, float]:
        """Calculate filesystem event rates.

        Returns:
            Tuple of (short_rate, long_rate, weighted_rate)
        """
        short_rate = len(self._fs_events_short) / self.fs_rate_short_window if self.fs_rate_short_window else 0.0
        long_rate = len(self._fs_events_long) / self.fs_rate_long_window if self.fs_rate_long_window else 0.0
        weighted_rate = (
            self.fs_rate_short_weight * short_rate
            + self.fs_rate_long_weight * long_rate
        )
        return short_rate, long_rate, weighted_rate

    def _get_lock_info(self) -> tuple[bool, Optional[int], str]:
        """Get lock file information.

        Returns:
            Tuple of (lock_present, lock_pid, lock_path)
        """
        lock_present = bool(self.lock_file.exists())
        lock_pid = None
        if lock_present:
            try:
                content = self.lock_file.read_text().strip()
                if content:
                    lock_pid = int(content.splitlines()[0])
            except Exception:
                pass
        return lock_present, lock_pid, str(self.lock_file)

    def _format_uptime(self, secs: int) -> str:
        """Format uptime seconds as HH:MM:SS."""
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _write_health(self):
        """Write health data to health.json file."""
        try:
            now = time.time()
            uptime_secs = int(now - self._health_started_at)

            db_last_operation, db_last_detail, db_last_iso, db_ops_last_minute = self._get_db_activity_info(now)
            db_ops_per_min = round(db_ops_last_minute / 1.0, 2)

            short_rate, long_rate, weighted_rate = self._calculate_fs_rates()
            lock_present, lock_pid, lock_path = self._get_lock_info()

            health_data = HealthData(
                pending_deletes=len(self._pending_deletes),
                pending_mods=len(self._pending_mods),
                last_error=self._last_error,
                pid=os.getpid(),
                last_error_at=int(self._last_error_at) if self._last_error_at else None,
                last_error_at_iso=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._last_error_at)) if self._last_error_at else None,
                last_error_age_secs=int(now - self._last_error_at) if self._last_error_at else None,
                started_at=int(self._health_started_at),
                started_at_iso=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._health_started_at)),
                uptime_secs=uptime_secs,
                uptime_hms=self._format_uptime(uptime_secs),
                beats=int(self._beat_count),
                avg_beats_per_min=db_ops_per_min,
                lock_present=lock_present,
                lock_pid=lock_pid,
                lock_path=lock_path,
                db_last_operation=db_last_operation,
                db_last_operation_detail=db_last_detail,
                db_last_operation_iso=db_last_iso,
                db_ops_last_minute=db_ops_last_minute,
                fs_rate_short=short_rate,
                fs_rate_long=long_rate,
                fs_rate_weighted=weighted_rate,
                fs_rate_short_window_secs=self.fs_rate_short_window,
                fs_rate_long_window_secs=self.fs_rate_long_window,
                fs_rate_short_weight=self.fs_rate_short_weight,
                fs_rate_long_weight=self.fs_rate_long_weight,
            )

            self.health_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.health_file, 'w') as f:
                json.dump(health_data.to_dict(), f)

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
    vault_cfg = config.get("vault")
    if not vault_cfg:
        raise ValueError("vault section is required in config (found: missing, expected: vault section with base_dir, wks_dir, etc.)")
    vault_path_str = vault_cfg.get("base_dir")
    if not vault_path_str:
        raise ValueError("vault.base_dir is required in config (found: missing, expected: path to Obsidian vault directory)")
    vault_path = expand_path(vault_path_str)
    base_dir = vault_cfg.get("wks_dir")
    if not base_dir:
        raise ValueError("vault.wks_dir is required in config (found: missing, expected: subdirectory name within vault, e.g., 'WKS')")

    # Monitor config
    monitor_cfg_obj = MonitorConfig.from_config_dict(config)
    monitor_rules = MonitorRules.from_config(monitor_cfg_obj)
    include_paths = [expand_path(p) for p in monitor_cfg_obj.include_paths]

    # DB config
    db_cfg = config.get("db")
    if not db_cfg:
        raise ValueError("db section is required in config (found: missing, expected: db section with type and uri)")
    mongo_uri = db_cfg.get("uri")
    if not mongo_uri:
        raise ValueError("db.uri is required in config (found: missing, expected: MongoDB connection URI string)")
    mongo_uri = str(mongo_uri)
    ensure_mongo_running(mongo_uri, record_start=True)

    client = MongoClient(mongo_uri)
    monitor_db_key = monitor_cfg_obj.database
    if not monitor_db_key:
        raise ValueError("monitor.database is required in config (found: missing, expected: 'database.collection' format, e.g., 'wks.monitor')")
    if "." not in monitor_db_key:
        raise ValueError(f"monitor.database must be in format 'database.collection' (found: {monitor_db_key!r}, expected: format like 'wks.monitor')")
    parts = monitor_db_key.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"monitor.database must be in format 'database.collection' (found: {monitor_db_key!r}, expected: format like 'wks.monitor' with both parts non-empty)")
    monitor_db_name, monitor_coll_name = parts
    monitor_collection = client[monitor_db_name][monitor_coll_name]

    # Vault settings from vault section (SPEC: vault.type="obsidian")
    # Simplified: only base_dir, wks_dir, update_frequency_seconds, type, database
    obsidian_log_max_entries = 500  # Default, not in vault section
    obsidian_active_files_max_rows = 100  # Default, not in vault section
    obsidian_source_max_chars = 40  # Default, not in vault section
    obsidian_destination_max_chars = 40  # Default, not in vault section
    obsidian_docs_keep = 50  # Default, not in vault section
    auto_project_notes = False  # Default, not in vault section

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
        monitor_rules=monitor_rules,
        mongo_uri=mongo_uri,
        monitor_collection=monitor_collection,
    )

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
