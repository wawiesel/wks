# Daemon Specification

The WKS daemon runs as a background service to monitor the filesystem and maintain the knowledge graph. It can be installed as a system service (launchd on macOS) or run manually.

**MCP Interface**:
- `wksm_daemon(action)` — Manage daemon (start, stop, restart, status, install, uninstall)

**CLI Interface**:
```bash
wksc daemon status           # Show daemon status and metrics (supports --live for auto-updating display)
wksc daemon start            # Start daemon (uses service if installed, otherwise starts directly)
wksc daemon stop             # Stop daemon
wksc daemon restart          # Restart daemon
wksc daemon install          # Install as system service (launchd on macOS)
wksc daemon uninstall        # Remove system service
```

**Start Behavior**:
The `wksc daemon start` command behaves differently depending on whether the service is installed:
- **If service is installed**: Starts the daemon via the system service manager (e.g., `launchctl` on macOS)
- **If service is not installed**: Starts the daemon directly as a background process.

This allows users to start the daemon without installing it as a service, which is useful for testing or temporary runs.

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
- Daemon monitors configured paths and updates monitor database
- Daemon maintains vault links and syncs with Obsidian
- Daemon provides MCP broker for AI agent access

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

