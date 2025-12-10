# Daemon Specification

## Purpose
Runtime worker that watches the filesystem and syncs changes to the monitor database. Runs in a background thread/process started by the system service (or manually). Provides start/stop/status only.

## Runtime Behavior
- Watches filesystem events (modified, created, deleted, moved) via watchdog observer.
- For each event, calls the equivalent of `wksc monitor sync <path>` to update the monitor database.
- Moves are treated as delete at old path then create at new path.
- Must handle non-existent paths (deletes) correctly.
- Runs continuously until stopped; single instance per configuration.

## Configuration
- Location: `{WKS_HOME}/config.json`.
- Section: `daemon`.
- All fields are required; no defaults:
  - `sync_interval_secs` (number > 0): how long to accumulate events before syncing.
  - `log_file` (string, relative): path (relative to `WKS_HOME`) for daemon stdout/stderr; entries must include severity.
  - `restrict_dir` (string): directory root to watch; use empty string to fall back to monitor filter include paths (no implicit default).
Example:
```json
{
  "daemon": {
    "sync_interval_secs": 5.0,
    "log_file": "logs/daemon.log",
    "restrict_dir": ""
  }
}
```

## CLI
- Entry: `wksc daemon`
- Output formats: `--display yaml` (default) or `--display json`

### status
- Command: `wksc daemon status`
- Behavior: Report running state, pid (if any), log path, recent warnings/errors.
- Output schema: `DaemonStatusOutput`.

### start
- Command: `wksc daemon start [--restrict <dir>]`
- Behavior: Start the daemon in the background (single instance). if restrict dir is provided, sets in daemon config.
- Output schema: `DaemonStartOutput`.

### stop
- Command: `wksc daemon stop`
- Behavior: Stop the running daemon instance.
- Output schema: `DaemonStopOutput`.

## MCP
- Commands mirror CLI:
  - `wksm_daemon_status`
  - `wksm_daemon_start`
  - `wksm_daemon_stop`
- Output format: JSON; structures mirror CLI outputs.

## Error Semantics
- All outputs must be schema-conformant; no partial success.
- Missing required fields or unknown state must surface as errors (no defaults/hedging).

## Formal Requirements
- DAEMON.1 — All daemon config fields required; no defaults in code.
- DAEMON.2 — Single running instance per configuration; `start` must fail if already running.
- DAEMON.3 — Events must be sent to monitor sync exactly as observed (filtering happens in monitor).
- DAEMON.4 — Moves must emit delete+create semantics.
- DAEMON.5 — Non-existent paths must be supported for deletes.
- DAEMON.6 — CLI and MCP return identical structures for equivalent commands.

