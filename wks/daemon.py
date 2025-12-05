"""
WKS daemon for monitoring file system and updating Obsidian.

Adds support for ~/.wks/config.json with include/exclude path control.
"""

import contextlib
import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from pymongo.collection import Collection

from .config import ConfigError, WKSConfig
from .constants import WKS_HOME_EXT
from .mcp_bridge import MCPBroker
from .mcp_paths import mcp_socket_path
from .monitor import (
    start_monitoring,  # Filesystem monitoring (via monitor package)
)
from .monitor_rules import MonitorRules
from .priority import calculate_priority
from .transform import TransformController
from .uri_utils import uri_to_path
from .utils import expand_path, file_checksum
from .vault.indexer import VaultLinkIndexer
from .vault.obsidian import ObsidianVault

logger = logging.getLogger(__name__)
try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover
    fcntl = cast(Any, None)

# Optional imports for MongoDB guard and DB activity tracking
# These may not exist in all environments and are mocked in tests
try:
    from .mongo_guard import MongoGuard  # type: ignore
except ImportError:
    MongoGuard = None  # type: ignore

try:
    from .db_activity import load_db_activity_history, load_db_activity_summary  # type: ignore
except ImportError:

    def load_db_activity_summary():  # type: ignore
        return None

    def load_db_activity_history(window_secs: int):  # type: ignore  # noqa: ARG001
        return []


try:
    from .mongo_utils import ensure_mongo_running  # type: ignore
except ImportError:

    def ensure_mongo_running(uri: str, record_start: bool = False):  # type: ignore
        pass


@dataclass
class HealthData:
    """Health data structure for daemon health.json file."""

    pending_deletes: int
    pending_mods: int
    last_error: str | None
    pid: int
    last_error_at: int | None
    last_error_at_iso: str | None
    last_error_age_secs: int | None
    started_at: int
    started_at_iso: str
    uptime_secs: int
    uptime_hms: str
    beats: int
    avg_beats_per_min: float
    lock_present: bool
    lock_pid: int | None
    lock_path: str
    db_last_operation: str | None
    db_last_operation_detail: str | None
    db_last_operation_iso: str | None
    db_ops_last_minute: int
    fs_rate_short: float
    fs_rate_long: float
    fs_rate_weighted: float
    fs_rate_short_window_secs: float
    fs_rate_long_window_secs: float
    fs_rate_short_weight: float
    fs_rate_long_weight: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


class WKSDaemon:
    """Daemon that monitors filesystem and updates Obsidian vault."""

    def __init__(
        self,
        config: WKSConfig,
        vault_path: Path,
        base_dir: str,
        monitor_paths: list[Path],
        monitor_rules: MonitorRules,
        auto_project_notes: bool = False,
        fs_rate_short_window_secs: float = 10.0,
        fs_rate_long_window_secs: float = 600.0,
        fs_rate_short_weight: float = 0.8,
        fs_rate_long_weight: float = 0.2,
        monitor_collection: Collection | None = None,
    ):
        """
        Initialize WKS daemon.

        Args:
            vault_path: Path to Obsidian vault
            monitor_paths: List of paths to monitor
        """
        self.config = config
        self.vault = ObsidianVault(vault_path, base_dir=base_dir)

        self._vault_indexer = VaultLinkIndexer.from_config(self.vault, config)
        # Git-based incremental scanning is fast, so we can check more frequently
        self._vault_sync_interval = float(self.config.vault.update_frequency_seconds)
        self._last_vault_sync = 0.0
        self.monitor_paths = [Path(p).expanduser().resolve() for p in monitor_paths]
        self.monitor_rules = monitor_rules
        self.observer = None
        self.auto_project_notes = auto_project_notes
        # Single-instance lock
        self.lock_file = Path.home() / WKS_HOME_EXT / "daemon.lock"
        self._lock_fh: Any | None = None  # File handle when opened
        # Maintenance (periodic tasks)
        self._last_prune_check = 0.0
        # Read prune interval from config, default to 5 minutes (300 seconds)
        self._prune_interval_secs = self.config.monitor.prune_interval_secs
        # Coalesce delete events to avoid temp-file save false positives
        self._pending_deletes: dict[str, float] = {}
        self._delete_grace_secs = 2.0
        # Coalesce modify/create bursts
        self._pending_mods: dict[str, dict[str, Any]] = {}
        self._mod_coalesce_secs = 0.6
        # Health
        self.health_file = Path.home() / WKS_HOME_EXT / "health.json"
        self._last_error: str | None = None
        self._last_error_at: float | None = None
        self._health_started_at = time.time()
        self._beat_count = 0
        # FS operation rate tracking
        self.fs_rate_short_window = max(float(fs_rate_short_window_secs), 1.0)
        self.fs_rate_long_window = max(float(fs_rate_long_window_secs), self.fs_rate_short_window)
        self.fs_rate_short_weight = float(fs_rate_short_weight)
        self.fs_rate_long_weight = float(fs_rate_long_weight)
        self._fs_events_short: deque[float] = deque()
        self._fs_events_long: deque[float] = deque()
        self.monitor_collection = monitor_collection
        self._mongo_guard: Any | None = None  # MongoGuard type, but may be None if import fails
        self._mcp_broker: MCPBroker | None = None
        self._mcp_socket = mcp_socket_path()

        # Initialize transform controller if transform config exists
        self._transform_controller: TransformController | None = None
        if self.config.transform:
            try:
                from .api.db.helpers import get_database

                transform_cfg = self.config.transform
                cache_location = expand_path(transform_cfg.cache.location)
                max_size_bytes = transform_cfg.cache.max_size_bytes

                db_name = transform_cfg.database.split(".")[0]
                db = get_database(db_name)
                self._transform_controller = TransformController(db, cache_location, max_size_bytes)
            except Exception:
                pass

    @staticmethod
    def _get_touch_weight(weight: float) -> float:
        min_weight = 0.001
        max_weight = 1.0

        if weight < min_weight:
            logger.warning("monitor.touch_weight %.6f below %.3f; using %.3f", weight, min_weight, min_weight)
            return min_weight

        if weight > max_weight:
            logger.warning("monitor.touch_weight %.6f above %.3f; using %.3f", weight, max_weight, max_weight)
            return max_weight

        return weight

    def _compute_touches_per_day(self, doc: dict[str, Any] | None, now: datetime, weight: float) -> float:
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

            managed_dirs = self.config.monitor.managed_directories
            priority_config = self.config.monitor.priority
            touch_weight = self._get_touch_weight(self.config.monitor.touch_weight)

            priority = calculate_priority(path, managed_dirs, priority_config)

            path_uri = path.as_uri()
            existing_doc = self.monitor_collection.find_one({"path": path_uri}, {"timestamp": 1, "touches_per_day": 1})
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
            max_docs = self.config.monitor.max_documents

            count = self.monitor_collection.count_documents({})
            if count <= max_docs:
                return

            extras = count - max_docs
            if extras > 0:
                # Find and remove the lowest priority documents
                lowest_priority_docs = (
                    self.monitor_collection.find({}, {"_id": 1, "priority": 1}).sort("priority", 1).limit(extras)
                )

                ids_to_delete = [doc["_id"] for doc in lowest_priority_docs]
                if ids_to_delete:
                    self.monitor_collection.delete_many({"_id": {"$in": ids_to_delete}})
        except Exception as e:
            self._set_error(f"monitor_db_limit_error: {e}")

    def _record_fs_event(self, timestamp: float | None = None) -> None:
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

    def _update_monitor_db_on_move(self, src: Path, dest: Path) -> None:
        """Update monitor database when file is moved."""
        if self.monitor_collection is None:
            return

        try:
            old_file_uri = src.resolve().as_uri()
            new_file_uri = dest.resolve().as_uri()

            # Check if old URI exists in monitor DB
            old_doc = self.monitor_collection.find_one({"path": old_file_uri})
            if old_doc:
                # Update path to new URI (preserving other fields)
                self.monitor_collection.update_one(
                    {"path": old_file_uri},
                    {"$set": {"path": new_file_uri}},
                )
            # If dest exists, ensure it's in monitor DB
            self._update_monitor_db(dest)
        except Exception as exc:
            self._set_error(f"monitor_db_update_error: {exc}")

    def _update_vault_db_on_move(self, old_uri: str, new_uri: str) -> None:
        """Update vault database links when file is moved."""
        if not (hasattr(self, "_vault_indexer") and self._vault_indexer):
            return

        try:
            updated_count = self._vault_indexer.update_links_on_file_move(old_uri, new_uri)
            if updated_count > 0:
                self._set_info(f"Updated {updated_count} vault links for moved file")
        except Exception as exc:
            self._set_error(f"vault_link_update_error: {exc}")

    def _update_transform_db_on_move(self, src: Path, dest: Path) -> None:
        """Update transform cache when file is moved."""
        if not self._transform_controller:
            return

        try:
            old_file_uri = src.resolve().as_uri()
            new_file_uri = dest.resolve().as_uri()
            updated_count = self._transform_controller.update_uri(old_file_uri, new_file_uri)
            if updated_count > 0:
                self._set_info(f"Updated {updated_count} transform cache entries for moved file")
        except Exception as exc:
            self._set_error(f"transform_db_update_error: {exc}")

    def _get_vault_base_path(self) -> Path | None:
        """Get vault base directory path if configured."""
        try:
            base_dir = self.config.vault.base_dir
            return Path(base_dir) if base_dir else None
        except Exception:
            pass
        return None

    def _log_move_operation(self, src: Path, dest: Path, tracked_src: bool, dest_is_file: bool) -> None:
        """Log file move operation if applicable.

        Args:
            src: Source path
            dest: Destination path
            tracked_src: Whether source is tracked
            dest_is_file: Whether destination is a file
        """
        if tracked_src or dest_is_file:
            try:
                self.vault.log_file_operation("moved", src, dest, tracked_files_count=self._get_tracked_files_count())
                self._bump_beat()
            except Exception:
                pass

    def _update_databases_on_move(self, src: Path, dest: Path, dest_is_file: bool) -> None:
        """Update all databases for a move operation.

        Args:
            src: Source path
            dest: Destination path
            dest_is_file: Whether destination is a file
        """
        if not dest_is_file:
            return

        from .uri_utils import convert_to_uri

        vault_base = self._get_vault_base_path()
        old_uri = convert_to_uri(src, vault_base)
        new_uri = convert_to_uri(dest, vault_base)

        self._update_monitor_db_on_move(src, dest)
        self._update_vault_db_on_move(old_uri, new_uri)
        self._update_transform_db_on_move(src, dest)

    def _update_monitor_db_for_move(self, src: Path, dest: Path, tracked_src: bool, dest_is_file: bool) -> None:
        """Update monitor DB entries for move operation.

        Args:
            src: Source path
            dest: Destination path
            tracked_src: Whether source is tracked
            dest_is_file: Whether destination is a file
        """
        if tracked_src and not self._should_ignore_by_rules(src):
            self._remove_from_monitor_db(src)
        if dest_is_file and not self._should_ignore_by_rules(dest):
            self._update_monitor_db(dest)

    def _handle_move_event(self, src_path: str, dest_path: str):
        """Handle file move event."""
        src = Path(src_path)
        dest = Path(dest_path)

        # Cancel any pending delete for destination (temp-file replace pattern)
        with contextlib.suppress(Exception):
            self._pending_deletes.pop(dest.resolve().as_posix(), None)

        tracked_src = self._monitor_has_path(src)
        dest_is_file = False
        try:
            dest_is_file = dest.exists() and dest.is_file()
        except Exception:
            dest_is_file = False

        # Log operation
        self._log_move_operation(src, dest, tracked_src, dest_is_file)

        # Update symlink target if tracked
        with contextlib.suppress(Exception):
            self.vault.update_link_on_move(src, dest)

        # Update all databases if destination is a file
        self._update_databases_on_move(src, dest, dest_is_file)

        # Update wiki links inside vault
        with contextlib.suppress(Exception):
            self.vault.update_vault_links_on_move(src, dest)

        # Update monitor DB (only if not ignored)
        self._update_monitor_db_for_move(src, dest, tracked_src, dest_is_file)

    def _handle_delete_event(self, path: Path):
        """Handle file delete event."""
        if not self._monitor_has_path(path):
            return
        with contextlib.suppress(Exception):
            self._pending_deletes[path.resolve().as_posix()] = time.time()

    def _handle_create_modify_event(self, path: Path, event_type: str):
        """Handle file create or modify event."""
        # Cancel any pending delete for same path
        with contextlib.suppress(Exception):
            self._pending_deletes.pop(path.resolve().as_posix(), None)

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

        # Install git hooks for vault link validation
        self._install_vault_git_hooks()

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
        if MongoGuard is None:
            return  # MongoGuard not available
        guard = self._mongo_guard
        if guard is None:
            from .api.db.helpers import get_database_client
            client = get_database_client()
            # MongoGuard needs the URI string, so we get it from the client
            uri = getattr(client, "uri", None) or str(client.address)
            guard = MongoGuard(uri, ping_interval=10.0)
            self._mongo_guard = guard
        guard.start(record_start=True)

    def _stop_mongo_guard(self):
        guard = self._mongo_guard
        if not guard:
            return
        with contextlib.suppress(Exception):
            guard.stop()

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
        with contextlib.suppress(Exception):
            broker.stop()

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
                self._maybe_sync_vault_links()
                self._write_health()
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _should_ignore_by_rules(self, path: Path) -> bool:
        try:
            return not self.monitor_rules.allows(path)
        except Exception:
            return False

    def _should_prune_entry(self, uri: str) -> tuple[bool, Path | None]:
        """Check if a monitor entry should be pruned.

        Args:
            uri: URI path from monitor entry

        Returns:
            Tuple of (should_prune, path_object) where path_object is None if URI conversion fails
        """
        # Convert URI to path for checking
        try:
            p = uri_to_path(uri)
        except Exception:
            return (False, None)

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

        return (missing or ignored, p)

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
                uri = doc.get("path")
                if not uri:
                    continue

                should_prune, _ = self._should_prune_entry(uri)
                if should_prune:
                    try:
                        self.monitor_collection.delete_one({"path": uri})
                        removed += 1
                    except Exception:
                        continue

            if removed:
                print(f"Monitor maintenance: pruned {removed} stale/excluded entries")
        except Exception as e:
            self._set_error(f"monitor_prune_error: {e}")

    def _process_expired_delete(self, pstr: str, p: Path) -> None:
        """Process a single expired delete event.

        Args:
            pstr: String path from pending deletes
            p: Path object for the file
        """
        # If the path exists again, skip logging delete
        if p.exists():
            self._pending_deletes.pop(pstr, None)
            return

        # Log deletion now
        try:
            self.vault.log_file_operation("deleted", p, tracked_files_count=self._get_tracked_files_count())
        except Exception as e:
            self._set_error(f"delete_log_error: {e}")

        self._remove_from_monitor_db(p)

        # Remove from transform DB - file no longer exists
        if self._transform_controller:
            try:
                file_uri = p.resolve().as_uri()
                removed_count = self._transform_controller.remove_by_uri(file_uri)
                if removed_count > 0:
                    self._set_info(f"Removed {removed_count} transform cache entries for deleted file")
            except Exception as exc:
                self._set_error(f"transform_db_delete_error: {exc}")

        # Only mark deletion if vault files actually reference this file
        try:
            has_vault_refs = self._vault_indexer.has_references_to(p) if self._vault_indexer else False
            if has_vault_refs:
                self.vault.mark_reference_deleted(p)
        except Exception as e:
            self._set_error(f"mark_ref_error: {e}")

        self._pending_deletes.pop(pstr, None)

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
                self._process_expired_delete(pstr, p)
            except Exception:
                # Best-effort
                with contextlib.suppress(Exception):
                    self._pending_deletes.pop(pstr, None)

    def _process_expired_mod(self, pstr: str, p: Path, etype: str) -> None:
        """Process a single expired modification event.

        Args:
            pstr: String path from pending mods
            p: Path object for the file
            etype: Event type (e.g., "modified", "created")
        """
        # Skip if file should be ignored
        if self._should_ignore_by_rules(p):
            self._pending_mods.pop(pstr, None)
            return

        # Only log if still exists and is file
        if p.exists() and p.is_file():
            try:
                self.vault.log_file_operation(etype, p, tracked_files_count=self._get_tracked_files_count())
                self._bump_beat()
            except Exception as e:
                self._set_error(f"ops_log_error: {e}")
            self._update_monitor_db(p)

            # Remove from transform DB if modified - content changed invalidates cache
            if etype == "modified" and self._transform_controller:
                try:
                    file_uri = p.resolve().as_uri()
                    removed_count = self._transform_controller.remove_by_uri(file_uri)
                    if removed_count > 0:
                        self._set_info(f"Removed {removed_count} transform cache entries for modified file")
                except Exception as exc:
                    self._set_error(f"transform_db_modified_error: {exc}")

        self._pending_mods.pop(pstr, None)

    def _maybe_flush_pending_mods(self):
        """Flush pending modification events after coalesce period."""
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
                self._process_expired_mod(pstr, p, etype)
            except Exception:
                with contextlib.suppress(Exception):
                    self._pending_mods.pop(pstr, None)

    def _maybe_sync_vault_links(self):
        if not getattr(self, "_vault_indexer", None):
            return
        now = time.time()
        if now - getattr(self, "_last_vault_sync", 0.0) < self._vault_sync_interval:
            return
        try:
            # Use incremental git-based scanning for efficiency
            self._vault_indexer.sync(incremental=True)
        except Exception as exc:
            self._set_error(f"vault_sync_error: {exc}")
        finally:
            self._last_vault_sync = now

    def _extract_db_summary_info(self, db_summary: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        """Extract DB activity info from summary.

        Args:
            db_summary: Summary dictionary

        Returns:
            Tuple of (last_operation, last_detail, last_iso)
        """
        try:
            db_last_iso = db_summary.get("timestamp_iso") or None
            db_last_operation = db_summary.get("operation") or None
            db_last_detail = db_summary.get("detail") or None
            return db_last_operation, db_last_detail, db_last_iso
        except Exception:
            return None, None, None

    def _extract_db_history_info(self, db_history: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None]:
        """Extract DB activity info from history.

        Args:
            db_history: History list

        Returns:
            Tuple of (last_operation, last_detail, last_iso)
        """
        if not db_history:
            return None, None, None
        try:
            last_item = db_history[-1]
            db_last_iso = last_item.get("timestamp_iso")
            db_last_operation = last_item.get("operation")
            db_last_detail = last_item.get("detail")
            return db_last_operation, db_last_detail, db_last_iso
        except Exception:
            return None, None, None

    def _count_db_ops_last_minute(self, db_history: list[dict[str, Any]], cutoff_minute: float) -> int:
        """Count DB operations in the last minute.

        Args:
            db_history: History list
            cutoff_minute: Timestamp cutoff for last minute

        Returns:
            Count of operations in last minute
        """
        count = 0
        for item in db_history:
            try:
                ts_val = float(item.get("timestamp", 0))
            except Exception:
                continue
            if ts_val >= cutoff_minute:
                count += 1
        return count

    def _get_db_activity_info(self, now: float) -> tuple[str | None, str | None, str | None, int]:
        """Get DB activity information from summary and history.

        Returns:
            Tuple of (last_operation, last_detail, last_iso, ops_last_minute)
        """
        db_summary = load_db_activity_summary()
        db_history_window = max(int(self.fs_rate_long_window), 600)
        db_history = load_db_activity_history(db_history_window)

        db_last_operation, db_last_detail, db_last_iso = self._extract_db_summary_info(db_summary)

        if db_last_operation is None:
            op, detail, iso = self._extract_db_history_info(db_history)
            if op is not None:
                db_last_operation, db_last_detail, db_last_iso = op, detail, iso

        cutoff_minute = now - 60.0
        db_ops_last_minute = self._count_db_ops_last_minute(db_history, cutoff_minute)

        self._beat_count = len(db_history)
        return db_last_operation, db_last_detail, db_last_iso, db_ops_last_minute

    def _calculate_fs_rates(self) -> tuple[float, float, float]:
        """Calculate filesystem event rates.

        Returns:
            Tuple of (short_rate, long_rate, weighted_rate)
        """
        short_rate = len(self._fs_events_short) / self.fs_rate_short_window if self.fs_rate_short_window else 0.0
        long_rate = len(self._fs_events_long) / self.fs_rate_long_window if self.fs_rate_long_window else 0.0
        weighted_rate = self.fs_rate_short_weight * short_rate + self.fs_rate_long_weight * long_rate
        return short_rate, long_rate, weighted_rate

    def _get_lock_info(self) -> tuple[bool, int | None, str]:
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
                last_error_at_iso=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._last_error_at))
                if self._last_error_at
                else None,
                last_error_age_secs=int(now - self._last_error_at) if self._last_error_at else None,
                started_at=int(self._health_started_at),
                started_at_iso=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._health_started_at)),
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
            with self.health_file.open("w") as f:
                json.dump(health_data.to_dict(), f)

            # Vault health page disabled
        except Exception:
            pass

    def _bump_beat(self) -> None:
        with contextlib.suppress(Exception):
            self._beat_count += 1

    def _set_error(self, msg: str):
        try:
            self._last_error = str(msg)
            self._last_error_at = time.time()
        except Exception:
            pass

    def _set_info(self, msg: str):
        # Placeholder for info logging to health/status if needed
        pass

    def _clean_stale_lock(self):
        """Clean up stale lock file if process is no longer running."""
        try:
            if self.lock_file.exists():
                try:
                    raw = self.lock_file.read_text().strip().splitlines()
                    stale_pid = int(raw[0]) if raw else None
                except Exception:
                    stale_pid = None
                if stale_pid and not self._pid_running(stale_pid):
                    with contextlib.suppress(Exception):
                        self.lock_file.unlink()
        except Exception:
            pass

    def _try_pidfile_lock(self):
        """Try to acquire lock using PID file (fallback when fcntl unavailable)."""
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

    def _try_advisory_lock(self):
        """Try to acquire POSIX advisory lock using fcntl."""
        try:
            self._lock_fh = self.lock_file.open("w")
            fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write PID and timestamp
            self._lock_fh.seek(0)
            self._lock_fh.truncate()
            self._lock_fh.write(f"{os.getpid()}\n")
            self._lock_fh.flush()
        except BlockingIOError:
            # Another process holds the lock
            raise RuntimeError("Another WKS daemon instance is already running.") from None
        except Exception as e:
            raise RuntimeError(f"Failed to acquire daemon lock: {e}") from e

    def _acquire_lock(self):
        """Acquire an exclusive file lock to ensure a single daemon instance."""
        # Ensure directory exists
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Clean up stale lock files
        self._clean_stale_lock()

        # Use PID file fallback if fcntl not available, otherwise use advisory lock
        if fcntl is None:
            self._try_pidfile_lock()
        else:
            self._try_advisory_lock()

    def _release_lock(self):
        """Release the single-instance lock."""
        try:
            if self._lock_fh and fcntl is not None:
                fcntl.flock(self._lock_fh.fileno(), fcntl.LOCK_UN)
                self._lock_fh.close()
                self._lock_fh = None
            # Best-effort cleanup
            if self.lock_file.exists():
                with contextlib.suppress(Exception):
                    self.lock_file.unlink()
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

    def _install_vault_git_hooks(self):
        """Install git hooks for vault link validation."""
        try:
            from .vault.git_hooks import install_hooks, is_hook_installed

            vault_path = self.vault.vault_path

            # Check if already installed
            if is_hook_installed(vault_path):
                logger.debug("Git hooks already installed")
                return

            # Install hooks
            if install_hooks(vault_path):
                logger.info("Installed git hooks for vault link validation")
            else:
                logger.warning("Failed to install git hooks")

        except RuntimeError as exc:
            # Not a git repo - that's okay, just skip hook installation
            logger.debug(f"Skipping git hook installation: {exc}")
        except Exception as exc:
            # Other errors - log but don't fail daemon startup
            logger.warning(f"Error installing git hooks: {exc}")


if __name__ == "__main__":
    import sys

    # Load and validate config
    try:
        config = WKSConfig.load()
    except ConfigError as e:
        print(str(e))
        raise SystemExit(2) from e

    # Vault config
    vault_path = Path(config.vault.base_dir)
    base_dir = config.vault.wks_dir

    # Monitor config
    monitor_cfg_obj = config.monitor
    monitor_rules = MonitorRules.from_config(monitor_cfg_obj)
    include_paths = [expand_path(p) for p in monitor_cfg_obj.include_paths]

    # DB config
    from .api.db.helpers import get_database_client, get_database

    client = get_database_client()
    # ensure_mongo_running needs URI - this is MongoDB-specific, so we get it from config
    if config.db.type == "mongo":
        from .api.db._mongo._DbConfigData import _DbConfigData
        if isinstance(config.db.data, _DbConfigData):
            mongo_uri = config.db.data.uri
            ensure_mongo_running(mongo_uri, record_start=True)

    monitor_db_key = monitor_cfg_obj.database
    # Validation already done in MonitorConfig
    monitor_db_name, monitor_coll_name = monitor_db_key.split(".", 1)
    db = get_database(monitor_db_name)
    monitor_collection = db[monitor_coll_name]

    auto_project_notes = False  # Default, not in vault section

    daemon = WKSDaemon(
        config=config,
        vault_path=vault_path,
        base_dir=base_dir,
        auto_project_notes=auto_project_notes,
        monitor_paths=include_paths,
        monitor_rules=monitor_rules,
        monitor_collection=monitor_collection,
    )

    print("Starting WKS daemon...")
    print("Press Ctrl+C to stop")

    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        sys.exit(0)
