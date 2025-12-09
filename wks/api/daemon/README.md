## Daemon API

This directory implements the daemon API for background filesystem monitoring. The daemon watches filesystem changes and syncs them to the monitor database.

### Architecture

**Platform abstraction**: Platform-specific code is in `_<platform>/` subdirectories. Each contains `_Impl.py` (implementation) and `_Data.py` (platform-specific config). The public `Daemon` class validates backend types and instantiates platform implementations via context manager.

**Event accumulation**: Platform implementations accumulate filesystem events (modified, created, deleted, moved) in internal data structures. Events are returned via `get_filesystem_events()` which clears the accumulator.

**Event collapsing**: Before syncing, collapse temporary operations (rapid move/delete/create sequences) into "real" operations. This happens in `get_filesystem_events()` or a separate `_collapse_events()` method.

**No filtering in daemon**: The daemon sends all events to `wks.api.monitor.cmd_sync()`. Monitor sync applies filtering using `explain_path()` and priority checks. This maintains a single source of truth for filter logic.

### Main Loop Pattern

Platform implementations in `run()` do the following:
1. Initialize filesystem watcher (platform-specific)
2. Loop while `_running` is True:
   - Sleep for `sync_interval_secs`
   - Call `get_filesystem_events()` to get accumulated events
   - Collapse temporary operations (move chains, create+delete, etc.)
   - Send each event path to `wks.api.monitor.cmd_sync()`
   - For moves: sync old_path (delete) then new_path (create)
3. Clean up watcher on exit

See `_darwin/_Impl.py` for reference implementation.

### Event Collapsing

Collapse patterns:
- **Move chains**: A→B→C becomes A→C
- **Move-back**: A→B→A collapses to nothing (or modify if content changed)
- **Create+delete**: Remove both (temporary file)
- **Multiple modifies**: Collapse to single modify

### Configuration

`DaemonConfig` uses `type/data` pattern like `DatabaseConfig`:

```json
{
  "daemon": {
    "type": "darwin",
    "sync_interval_secs": 5.0,
    "data": { /* platform-specific */ }
  }
}
```

**Backend registry**: `_BACKEND_REGISTRY` in `DaemonConfig.py` is the only place platform types are enumerated. To add a platform:
1. Add entry to `_BACKEND_REGISTRY` mapping platform name to config data class
2. Create `_<platform>/` with `_Data.py` and `_Impl.py`
3. Rest works via dynamic imports

### Service Management

Platform implementations provide service management methods (optional, raise `NotImplementedError` if unsupported):
- `install_service()` / `uninstall_service()`: Install/remove system service
- `get_service_status()`: Get status (installed, running, PID)
- `start_service()` / `stop_service()`: Start/stop via service manager

**Execution modes**: `wksc daemon start` chooses:
- **Service mode**: If installed, runs via service manager (launchctl on macOS)
- **Direct mode**: If not installed, runs as detached background process

### FilesystemEvents

`FilesystemEvents` dataclass encapsulates events:
- `modified`, `created`, `deleted`: Lists of file paths (strings)
- `moved`: List of `(old_path, new_path)` tuples
- Helper methods: `is_empty()`, `total_count()`
