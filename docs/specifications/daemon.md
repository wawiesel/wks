# Daemon Specification

The WKS daemon runs as a background service to monitor the filesystem and maintain the knowledge graph. It can be installed as a system service (launchd on macOS) or run manually.

**MCP Interface**:
- `wksm_daemon(action)` — Manage daemon (start, stop, restart, status, install, uninstall)

**CLI Interface**:
```bash
wksc daemon status           # Show daemon status and metrics
wksc daemon start            # Start daemon (idempotent - ensures running, restarts if already running)
wksc daemon stop             # Stop daemon
wksc daemon restart          # Restart daemon with full reload (unloads and reloads service)
wksc daemon install          # Install as system service (launchd on macOS)
wksc daemon uninstall        # Remove system service
```

**Start vs Restart Behavior**:

**`wksc daemon start`** (idempotent - ensures daemon is running):
- **If service is installed and loaded**: Uses `launchctl kickstart -k`
  - Kills and restarts the process if already running
  - Starts the process if not running
  - Does NOT reload the plist file (service stays loaded in launchctl)
- **If service is installed but not loaded**: Bootstraps the service (loads plist and starts)
- **If service is not installed**: Starts daemon directly as background process

**`wksc daemon restart`** (full reload):
- **Always stops first**: Unloads service from launchctl (if service) or kills process (if direct)
- **Then starts**: Reloads plist into launchctl and starts fresh (if service) or starts new process (if direct)
- Ensures the service configuration is completely reloaded from the plist file

**Key Difference**: `start` uses `kickstart -k` which restarts the process without reloading the plist. `restart` performs a full unload/reload cycle, ensuring plist changes are picked up.

**When to use**:
- Use **start** for "ensure running" - safe to run multiple times, will restart process if needed
- Use **restart** when you need to reload plist configuration or want a clean reload cycle

**Status Output**:
The `status` command displays:
- Daemon process information (PID, running state)
- Warnings and errors from the daemon status file
- Service installation status (if installed as system service)

**Installation**:
The `daemon install` command automatically detects the operating system and installs the appropriate service mechanism:
- **macOS**: Creates a launchd service (`.plist` file in `~/Library/LaunchAgents/`) that automatically starts the daemon on login and keeps it running
- **Other OSes**: Support for additional operating systems will be added in the future

The service can be managed via system-specific tools (e.g., `launchctl` on macOS) or through the `wksc daemon` commands. The installation process reads daemon configuration from `config.json` to determine service parameters.

**Manual Execution**:
The daemon can be run directly without installing as a service using `wksc daemon start`. This is useful for development, testing, or one-off runs.

When started without a service installation, the daemon will:
- Load configuration from `{WKS_HOME}/config.json`
- Detect the operating system and use the appropriate backend implementation
- Run in the background as a detached process
- Write status to `{WKS_HOME}/daemon.json`
- Create a lock file at `{WKS_HOME}/daemon.lock` to prevent multiple instances

**Note**: When running without a service, ensure only one instance is running at a time. The lock file prevents concurrent execution, but if a previous instance crashed without cleaning up the lock file, you may need to manually remove `{WKS_HOME}/daemon.lock` before starting a new instance.

**Behavior**:
- Only one daemon instance can run at a time (enforced via lock file at `{WKS_HOME}/daemon.lock`)
- Daemon monitors the filesystem for changes and automatically performs the same operations that users could run manually via CLI commands

**Purpose**:
The daemon automates filesystem monitoring operations. Everything the daemon does could be done manually by running CLI commands, but the daemon performs these operations automatically in response to filesystem events.

**File System Event Handling**:

The daemon watches configured paths and automatically triggers monitor sync operations when files are created, deleted, or moved. These are the same operations a user would perform manually:

1. **File Move** (OLD_LOC → NEW_LOC):
   - Automatically performs: `wksc monitor sync DIR_OF_OLD_LOC` - Updates the old location directory, removing the old file entry from the monitor database
   - Automatically performs: `wksc monitor sync NEW_LOC` - Updates the new location, adding the file entry to the monitor database

2. **File Creation**:
   - Automatically performs: `wksc monitor sync NEW_LOC` - Updates the location where the file was created, adding the new file entry to the monitor database

3. **File Deletion**:
   - Automatically performs: `wksc monitor sync DIR_OF_OLD_LOC` - Updates the directory where the file was deleted, removing the file entry from the monitor database

The daemon uses the monitor API's `cmd_sync()` function internally (the same function used by `wksc monitor sync`), ensuring the monitor database stays synchronized with the actual filesystem state without requiring manual intervention.

**Daemon Status File**:
The daemon writes a simple status file at `{WKS_HOME}/daemon.json` (where `WKS_HOME` defaults to `~/.wks` if not set via environment variable) containing warnings and errors for display in `wksc daemon status`. The file structure is:

```json
{
  "pid": 12345,
  "warnings": [
    {"timestamp": "2025-12-05T12:00:00Z", "message": "warning message 1"},
    {"timestamp": "2025-12-05T12:01:00Z", "message": "warning message 2"}
  ],
  "errors": [
    {"timestamp": "2025-12-05T12:00:00Z", "message": "error message 1"},
    {"timestamp": "2025-12-05T12:01:00Z", "message": "error message 2"}
  ],
  "last_updated": "2025-12-05T12:00:00Z"
}
```

- `pid` (integer, optional): Process ID of the running daemon
- `warnings` (array of objects): List of warning entries, each containing:
  - `timestamp` (string, ISO 8601): When the warning occurred
  - `message` (string): Warning message text
- `errors` (array of objects): List of error entries, each containing:
  - `timestamp` (string, ISO 8601): When the error occurred
  - `message` (string): Error message text
- `last_updated` (string, ISO 8601): Timestamp when the status file was last updated

The daemon status file is used by `wksc daemon status` to:
- Determine if the daemon is running (check if PID is valid and process exists)
- Display any warnings or errors that need user attention, including when they occurred
- Distinguish between current and past issues based on timestamps

The file is written periodically by the daemon and should be kept simple - it's not a metrics log, just a way to surface issues to users. The daemon should clear resolved warnings/errors from the arrays when they are no longer relevant.
