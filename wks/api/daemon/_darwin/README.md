# Darwin (macOS) Backend Implementation

This directory contains the macOS-specific implementation of the daemon API using FSEvents for filesystem monitoring and launchd for service management.

## macOS-Specific Details

**Filesystem Monitoring**: macOS uses FSEvents for efficient filesystem change notifications. The `watchdog` library provides a cross-platform interface to FSEvents that we use for filesystem watching.

**Service Management**: macOS uses launchd for service management. Services are defined via plist files in `~/Library/LaunchAgents/` and managed via `launchctl` commands.

## Implementation Strategy

### Filesystem Watching

Use `watchdog` library's `Observer` and `FileSystemEventHandler` for filesystem monitoring:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

class _DaemonEventHandler(FileSystemEventHandler):
    """Handle filesystem events and accumulate them."""
    
    def __init__(self, event_accumulator):
        self.accumulator = event_accumulator
    
    def on_modified(self, event):
        if not event.is_directory:
            self.accumulator.add_modified(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory:
            self.accumulator.add_created(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.accumulator.add_deleted(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self.accumulator.add_moved(event.src_path, event.dest_path)
```

**Watch Scope**: Watch all paths that might be relevant. FSEvents is efficient and can handle large directory trees. Don't pre-filter based on monitor config - that happens in monitor sync.

**Event Deduplication**: FSEvents may emit duplicate events. Track events with timestamps and deduplicate within the sync interval.

### Event Accumulation

Maintain internal data structures to accumulate events:

```python
class _EventAccumulator:
    """Accumulate filesystem events with deduplication."""
    
    def __init__(self):
        self._modified: set[str] = set()
        self._created: set[str] = set()
        self._deleted: set[str] = set()
        self._moved: dict[str, str] = {}  # old_path -> new_path
        self._event_times: dict[str, float] = {}  # path -> timestamp
    
    def add_modified(self, path: str):
        # Deduplicate: if path was created/deleted recently, handle accordingly
        if path in self._deleted:
            # File was deleted then recreated - treat as create
            self._deleted.remove(path)
            self._created.add(path)
        elif path not in self._created:
            self._modified.add(path)
    
    def add_created(self, path: str):
        # If path was deleted, this is a recreate - keep as create
        if path in self._deleted:
            self._deleted.remove(path)
        self._created.add(path)
    
    def add_deleted(self, path: str):
        # If path was created recently, remove it (temporary file)
        if path in self._created:
            self._created.remove(path)
            return  # Temporary file, ignore
        # If path was moved, track the deletion at old location
        if path in self._moved.values():
            # This is the new location being deleted - treat as delete at old location
            old_path = next(k for k, v in self._moved.items() if v == path)
            del self._moved[old_path]
            self._deleted.add(old_path)
        else:
            self._deleted.add(path)
    
    def add_moved(self, old_path: str, new_path: str):
        # Handle move chains and temporary moves
        if old_path in self._moved:
            # Chain move: A->B->C becomes A->C
            actual_old = next(k for k, v in self._moved.items() if v == old_path)
            del self._moved[actual_old]
            self._moved[actual_old] = new_path
        else:
            self._moved[old_path] = new_path
    
    def get_and_clear(self) -> FilesystemEvents:
        """Get accumulated events and clear accumulator."""
        events = FilesystemEvents(
            modified=list(self._modified),
            created=list(self._created),
            deleted=list(self._deleted),
            moved=[(old, new) for old, new in self._moved.items()],
        )
        self._modified.clear()
        self._created.clear()
        self._deleted.clear()
        self._moved.clear()
        self._event_times.clear()
        return events
```

### Event Collapsing

Collapse temporary operations before returning events:

**Temporary moves**: If a file is moved and then moved back (or deleted) within the sync interval, collapse:
- Move A→B followed by move B→A → collapse to nothing (or modify if content changed)
- Move A→B followed by delete B → collapse to delete A

**Rapid create/delete**: If a file is created and deleted within the sync interval, remove both (temporary file).

**Rapid modify sequences**: Multiple modifications to the same file within the sync interval collapse to a single modify event.

**Implementation**: Add a `_collapse_events()` method that processes the accumulated events before returning:

```python
def _collapse_events(self, events: FilesystemEvents) -> FilesystemEvents:
    """Collapse temporary operations into real operations."""
    # Track move chains
    move_map: dict[str, str] = {}  # old -> new
    for old, new in events.moved:
        if new in move_map.values():
            # Chain detected: A->B->C becomes A->C
            actual_old = next(k for k, v in move_map.items() if v == old)
            del move_map[actual_old]
            move_map[actual_old] = new
        else:
            move_map[old] = new
    
    # Check for move-back patterns (A->B->A)
    final_moves = []
    for old, new in move_map.items():
        if new in move_map and move_map[new] == old:
            # Moved back - remove both
            continue
        final_moves.append((old, new))
    
    # Check for create+delete (temporary files)
    created_set = set(events.created)
    deleted_set = set(events.deleted)
    temp_files = created_set & deleted_set
    final_created = [p for p in events.created if p not in temp_files]
    final_deleted = [p for p in events.deleted if p not in temp_files]
    
    return FilesystemEvents(
        modified=events.modified,
        created=final_created,
        deleted=final_deleted,
        moved=final_moves,
    )
```

### Main Loop Implementation

The `run()` method should:

1. **Initialize filesystem watcher**: Set up `Observer` with event handler
2. **Start watching**: Begin watching filesystem (watch all relevant paths)
3. **Main loop**: Periodically get accumulated events and sync them
4. **Graceful shutdown**: Stop observer and clean up on `stop()`

```python
def run(self) -> None:
    """Run the daemon main loop."""
    from watchdog.observers import Observer
    from ...monitor.cmd_sync import cmd_sync
    
    self._running = True
    accumulator = _EventAccumulator()
    handler = _DaemonEventHandler(accumulator)
    observer = Observer()
    
    # Watch all paths (FSEvents is efficient)
    # TODO: Determine watch paths from monitor config if needed
    watch_paths = ["/"]  # Watch everything, filter in sync
    
    for path in watch_paths:
        observer.schedule(handler, path, recursive=True)
    
    observer.start()
    
    try:
        while self._running:
            time.sleep(self.config.sync_interval_secs)
            
            # Get accumulated events
            events = accumulator.get_and_clear()
            
            # Collapse temporary operations
            events = self._collapse_events(events)
            
            if events.is_empty():
                continue
            
            # Send events to monitor sync
            for path in events.modified:
                cmd_sync(path)
            for path in events.created:
                cmd_sync(path)
            for path in events.deleted:
                cmd_sync(path)  # Monitor sync handles non-existent paths
            for old_path, new_path in events.moved:
                cmd_sync(old_path)  # Delete at old location
                cmd_sync(new_path)  # Create at new location
    finally:
        observer.stop()
        observer.join()
```

### Service Management

**launchd Integration**: The `_launchd.py` module provides helper functions for launchd service management:

- `install_service()`: Creates plist file and bootstraps service
- `uninstall_service()`: Unloads service and removes plist
- `get_service_status()`: Checks if service is installed and running
- `_create_plist_content()`: Generates launchd plist XML

**Plist Structure**: The plist file defines:
- `Label`: Service identifier (reverse DNS format)
- `ProgramArguments`: Python module to run (`wks.api.daemon._darwin._Impl`)
- `WorkingDirectory`: WKS_HOME
- `EnvironmentVariables`: PYTHONPATH for project root
- `RunAtLoad`: Whether to start on load (from config)
- `KeepAlive`: Whether to restart on exit (from config)
- `StandardOutPath` / `StandardErrorPath`: Log file path

**Service Commands**:
- `launchctl bootstrap`: Load and start service
- `launchctl bootout`: Unload service
- `launchctl kickstart -k`: Restart service (kills if running)
- `launchctl print`: Get service status

**Implementation Notes**:
- Use `gui/{uid}/` domain for user services (not `system/`)
- Check if service is loaded before bootstrapping
- Verify service started by checking for PID
- Handle "already stopped" errors gracefully (idempotent operations)

## Configuration

Darwin configuration uses the `_DaemonConfigData` class:

```json
{
  "daemon": {
    "type": "darwin",
    "sync_interval_secs": 5.0,
    "data": {
      "label": "com.example.wks.daemon",
      "log_file": "logs/daemon.log",
      "keep_alive": true,
      "run_at_load": false
    }
  }
}
```

**Fields**:
- `label` (string, required): Launchd service identifier in reverse DNS format (e.g., "com.example.wks.daemon"). Must have at least 2 parts separated by dots.
- `log_file` (string, required): Path to log file relative to WKS_HOME. Must be relative (not absolute).
- `keep_alive` (boolean, required): Whether launchd should auto-restart the daemon if it exits.
- `run_at_load` (boolean, required): Whether the service should start automatically when installed.

## Implementation Details

The `_Impl` class in `_Impl.py` implements the abstract interface defined in `_AbstractImpl.py`. It:
- Uses `watchdog.Observer` for filesystem monitoring
- Accumulates events in internal data structures
- Collapses temporary operations before syncing
- Manages launchd service lifecycle via `_launchd` helpers

**Event Handling**: The implementation should handle FSEvents efficiently:
- FSEvents may emit events for directories - filter to files only
- FSEvents may emit duplicate events - deduplicate within sync interval
- FSEvents may emit move events as separate delete/create - normalize to move events

**Service Management**: The implementation delegates to `_launchd` helpers for service operations. The helpers handle:
- Plist file creation and management
- launchctl command execution
- Error handling and status checking

**Note**: This implementation is internal. Application code should use the public `Daemon` API from `wks.api.daemon.Daemon`. If you need platform-specific details, access them from the backend's config data: `daemon_config.data.label` (with proper type checking).

