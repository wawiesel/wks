# Daemon Specification

## Purpose
Manage filesystem-monitoring daemon: install/uninstall, start/stop, status. Consistent CLI/MCP outputs.

## Daemon Runtime Behavior

When running, the daemon monitors the filesystem and automatically synchronizes changes to the monitor database. The daemon:

- **Monitors filesystem events**: Watches for file modifications, creations, deletions, and moves
- **Calls monitor sync**: For each filesystem event, invokes the equivalent of `wksc monitor sync <path>` to update the monitor database
- **Handles file operations**:
  - **Modified**: Calls monitor sync for the modified file
  - **Created**: Calls monitor sync for the newly created file
  - **Deleted**: Calls monitor sync for the deleted file path (must support non-existent paths)
  - **Moved**: Treated as two operations: delete at old location, then create at new location
- **Runs continuously**: The daemon runs indefinitely until stopped, processing filesystem events as they occur

**Note**: The monitor sync API (`wks.api.monitor.cmd_sync`) must support paths that do not currently exist to handle file deletion events. When syncing a non-existent path, the monitor database should remove or mark the corresponding entry as deleted.

## Configuration File Structure
- Location: `{WKS_HOME}/config.json` (override via `WKS_HOME`)
- Composition: Uses `type/data` pattern similar to database configuration. All fields required; no defaults in code.
- Logging: single `log_file` path (relative to `WKS_HOME`) captures stdout/stderr; entries MUST annotate severity (info/warn/error) within that file.

The daemon configuration uses a platform-specific structure:

```json
{
  "daemon": {
    "type": "darwin",
    "data": {
      "label": "com.example.wks.daemon",
      "log_file": "logs/daemon.log",
      "keep_alive": true,
      "run_at_load": false
    }
  }
}
```

**Configuration Fields**:
- `type`: Platform/service manager type (e.g., `"darwin"` for macOS launchd). Must match a supported backend.
- `data`: Platform-specific configuration object. Structure depends on `type`.

**Platform-Specific Data (darwin/macOS)**:
- `label`: Launchd service identifier in reverse DNS format (e.g., `"com.example.wks.daemon"`). Required.
- `log_file`: Path to log file relative to `WKS_HOME`. Required. Must be relative (not absolute).
- `keep_alive`: Boolean indicating whether launchd should auto-restart the daemon if it exits. Required.
- `run_at_load`: Boolean indicating whether the service should start automatically when installed. Required.

## Normative Schema
- Canonical output schema: `docs/specifications/daemon_output.schema.json`.
- Implementations MUST validate outputs against this schema; unknown fields are rejected.

## CLI

- Entry: `wksc daemon`
- Output formats: `--display yaml` (default) or `--display json`

### status
- Command: `wksc daemon status`
- Behavior: Show daemon process/service status and any recorded warnings/errors.
- Output schema: `DaemonStatusOutput`.

### run
- Command: `wksc daemon run [--restrict <dir>]`
- Behavior: Run the daemon in the foreground, monitoring the filesystem and syncing changes to the monitor database. The daemon runs until interrupted (Ctrl+C).
- Parameters:
  - `--restrict <dir>`: (Optional) Restrict monitoring to the specified directory and its subdirectories. Useful for testing. If not specified, monitors all paths configured in `monitor.filter.include_paths`.
- Single instance: Only one daemon can run per configuration at a time. If a daemon is already running (detected via lock file or service status), the command fails with an error.
- Output schema: None (runs interactively, not a StageResult command).

### start
- Command: `wksc daemon start`
- Behavior: Start daemon via system service manager (if service is installed). If the service is already running, it restarts it. If service is not installed, the command fails with an error (use `wksc daemon run` to run without a service).
- Output schema: `DaemonStartOutput`.

### stop
- Command: `wksc daemon stop`
- Behavior: Stop daemon (if running as a service).
- Output schema: `DaemonStopOutput`.

### install
- Command: `wksc daemon install [--restrict <dir>]`
- Behavior: Install as system service. The service will run the daemon when started.
- Parameters:
  - `--restrict <dir>`: (Optional) Restrict monitoring to the specified directory and its subdirectories. This restriction is stored in the service configuration and applies when the service runs.
- Output schema: `DaemonInstallOutput`.

### uninstall
- Command: `wksc daemon uninstall`
- Behavior: Remove system service.
- Output schema: `DaemonUninstallOutput`.

## MCP
- Commands mirror CLI:
  - `wksm_daemon_status`
  - `wksm_daemon_start`
  - `wksm_daemon_stop`
  - `wksm_daemon_install`
  - `wksm_daemon_uninstall`
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Unknown/invalid state or schema violation returns schema-conformant error; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- DAEMON.1 — All daemon config fields required; no defaults in code.
- DAEMON.2 — Commands must emit schema-validated outputs (status/start/stop/install/uninstall).
- DAEMON.3 — CLI/MCP parity: same data and structure for equivalent commands.
- DAEMON.4 — Errors are schema-conformant; no partial success.
- DAEMON.5 — `wksc daemon run` MUST run the daemon in the foreground, monitoring filesystem events and calling the monitor sync API (`wks.api.monitor.cmd_sync`) for each event. Only one daemon instance can run per configuration at a time.
- DAEMON.6 — When running, the daemon MUST monitor filesystem events and call the monitor sync API (`wks.api.monitor.cmd_sync`) for each event: file modifications, creations, deletions, and moves. File moves MUST be treated as delete at old location followed by create at new location.
- DAEMON.7 — The monitor sync API MUST support paths that do not currently exist to handle file deletion events. When syncing a non-existent path, the monitor database entry for that path MUST be removed or marked as deleted.
- DAEMON.8 — The `--restrict <dir>` parameter MUST limit filesystem monitoring to the specified directory and its subdirectories, overriding the configured `monitor.filter.include_paths` when present.
