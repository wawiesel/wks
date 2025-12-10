# Darwin (macOS) Backend Implementation

This directory contains the macOS-specific implementation of the service API using FSEvents for filesystem monitoring and launchd for service management.

## macOS-Specific Details

**Filesystem Monitoring**: macOS uses FSEvents for efficient filesystem change notifications. The `watchdog` library provides a cross-platform interface to FSEvents that we use for filesystem watching.

**Service Management**: macOS uses launchd for service management. Services are defined via plist files in `~/Library/LaunchAgents/` and managed via `launchctl` commands.

## Implementation Strategy

### Filesystem Watching

The implementation uses `watchdog` library's `Observer` and `FileSystemEventHandler` for filesystem monitoring. See `_Impl.py` for the actual implementation.

**Watch Scope**: The service watches paths determined by:
1. `restrict_dir` parameter (if provided to `run()`)
2. `WKS_SERVICE_RESTRICT_DIR` environment variable (if set by service installation)
3. Configured `monitor.filter.include_paths` (fallback)

**Event Handling**: The `_ServiceEventHandler` class (nested in `_Impl`) accumulates events in sets/dictionaries:
- `_modified`: Set of modified file paths
- `_created`: Set of created file paths
- `_deleted`: Set of deleted file paths
- `_moved`: Dictionary mapping old_path -> new_path

Events are accumulated and returned via `get_and_clear_events()` which clears the accumulator after returning.

### Event Accumulation

The `_ServiceEventHandler` class (nested in `_Impl`) accumulates events in internal sets/dictionaries:
- `_modified`: Set of modified file paths
- `_created`: Set of created file paths
- `_deleted`: Set of deleted file paths
- `_moved`: Dictionary mapping old_path -> new_path

Events are accumulated and returned via `get_and_clear_events()` which clears the accumulator after returning.

**Event Collapsing**: TODO - The implementation currently does not collapse temporary operations (move chains, create+delete pairs, etc.). This should be added in the future to reduce unnecessary monitor sync calls.

### Main Loop Implementation

The `run(restrict_dir)` method:
1. Determines paths to watch (restrict_dir parameter, WKS_SERVICE_RESTRICT_DIR env var, or configured paths)
2. Initializes `watchdog.Observer` with `_ServiceEventHandler`
3. Schedules observer to watch determined paths recursively
4. Enters main loop:
   - Sleeps for `sync_interval_secs`
   - Gets accumulated events via `get_and_clear_events()`
   - Calls `wks.api.monitor.cmd_sync()` for each event path
   - For moves: syncs old_path (delete) then new_path (create)
5. Handles KeyboardInterrupt gracefully and stops observer

### Service Management

**launchd Integration**: Service management methods are implemented directly in `_Impl` class:
- `install_service()`: Creates plist file and bootstraps service. Accepts `restrict_dir` parameter which is stored as `WKS_SERVICE_RESTRICT_DIR` environment variable in the plist.
- `uninstall_service()`: Unloads service and removes plist
- `get_service_status()`: Checks if service is installed and running (including PID)
- `start_service()`: Starts service via launchctl (bootstrap if not loaded, kickstart if loaded)
- `stop_service()`: Stops service via launchctl bootout
- `_create_plist_content()`: Static method that generates launchd plist XML

**Plist Structure**: The plist file defines:
- `Label`: Service identifier (reverse DNS format, from config)
- `ProgramArguments`: Python module to run (`wks.api.service._darwin._Impl`)
- `WorkingDirectory`: WKS_HOME
- `EnvironmentVariables`: 
  - `PYTHONPATH`: Project root directory
  - `WKS_SERVICE_RESTRICT_DIR`: (Optional) Directory to restrict monitoring to
- `RunAtLoad`: Whether to start on load (from config)
- `KeepAlive`: Whether to restart on exit (from config)
- `StandardOutPath` / `StandardErrorPath`: Log file path (relative to WKS_HOME)

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

Darwin configuration uses the `_Data` class:

```json
{
  "service": {
    "type": "darwin",
    "sync_interval_secs": 5.0,
    "data": {
      "label": "com.example.wks.service",
      "log_file": "logs/service.log",
      "keep_alive": true,
      "run_at_load": false
    }
  }
}
```

**Fields**:
- `label` (string, required): Launchd service identifier in reverse DNS format (e.g., "com.example.wks.service"). Must have at least 2 parts separated by dots.
- `log_file` (string, required): Path to log file relative to WKS_HOME. Must be relative (not absolute).
- `keep_alive` (boolean, required): Whether launchd should auto-restart the service if it exits.
- `run_at_load` (boolean, required): Whether the service should start automatically when installed.

## Implementation Details

The `_Impl` class in `_Impl.py` implements the abstract interface defined in `_AbstractImpl.py`. It:
- Uses `watchdog.Observer` for filesystem monitoring
- Accumulates events in `_ServiceEventHandler` (nested class)
- Calls `wks.api.monitor.cmd_sync()` for each filesystem event
- Manages launchd service lifecycle directly (no separate `_launchd` module)

**Event Handling**: The implementation handles FSEvents:
- Filters to files only (ignores directory events)
- Accumulates events in sets/dictionaries for deduplication
- Returns accumulated events via `get_filesystem_events()` which clears the accumulator

**Service Management**: The implementation handles launchd operations directly:
- Plist file creation and management (via `_create_plist_content()` static method)
- launchctl command execution (bootstrap, bootout, kickstart, print)
- Error handling and status checking
- Supports `--restrict` directory via `WKS_SERVICE_RESTRICT_DIR` environment variable

**Note**: This implementation is internal. Application code should use the public `Service` API from `wks.api.service.Service`. If you need platform-specific details, access them from the backend's config data: `service_config.data.label` (with proper type checking).

