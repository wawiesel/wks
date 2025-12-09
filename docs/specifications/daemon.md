# Daemon Specification

## Purpose
Manage filesystem-monitoring daemon: install/uninstall, start/stop/restart, status. Consistent CLI/MCP outputs.

## Configuration File Structure
- Location: `{WKS_HOME}/config.json` (override via `WKS_HOME`)
- Composition: Uses `daemon` block as defined in `docs/specifications/wks.md`; all fields required; no defaults in code.
- Logging: single `log_file` path (relative to `WKS_HOME`) captures stdout/stderr; entries MUST annotate severity (info/warn/error) within that file.

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

### start
- Command: `wksc daemon start`
- Behavior: Ensure daemon is running (idempotent).
- Output schema: `DaemonStartOutput`.

### stop
- Command: `wksc daemon stop`
- Behavior: Stop daemon.
- Output schema: `DaemonStopOutput`.

### restart
- Command: `wksc daemon restart`
- Behavior: Full stop + start cycle.
- Output schema: `DaemonRestartOutput`.

### install
- Command: `wksc daemon install`
- Behavior: Install as system service.
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
  - `wksm_daemon_restart`
  - `wksm_daemon_install`
  - `wksm_daemon_uninstall`
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Unknown/invalid state or schema violation returns schema-conformant error; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- DAEMON.1 — All daemon config fields required; no defaults in code.
- DAEMON.2 — Commands must emit schema-validated outputs (status/start/stop/restart/install/uninstall).
- DAEMON.3 — CLI/MCP parity: same data and structure for equivalent commands.
- DAEMON.4 — Errors are schema-conformant; no partial success.
