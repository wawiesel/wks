# Service Specification

## Purpose
Platform-dependent installer/manager for the daemon. Provides install/uninstall/start/stop/status via the OS service manager (e.g., launchd on macOS). Ensures the daemon is running; the daemon performs the actual filesystem monitoring.

## Responsibilities
- Install/uninstall the daemon as a system service for the current platform.
- Start/stop the installed daemon via the platform’s service manager.
- Report installation/running status (including log path, warnings/errors recorded by the daemon).
- Persist and pass through an optional restrict directory to the daemon at launch.

## Configuration
- Location: `{WKS_HOME}/config.json` (override via `WKS_HOME`)
- Section: `service`
- Uses `type/data` pattern; all fields required; no defaults in code.
- Logging: single standardized log path `{WKS_HOME}/logs/service.log` (not configurable); entries MUST annotate severity (INFO/WARN/ERROR/DEBUG).

Example (darwin):
```json
{
  "service": {
    "type": "darwin",
    "data": {
      "label": "com.example.wks.service",
      "keep_alive": true,
      "run_at_load": false,
      "restrict_dir": null
    }
  }
}
```

**Configuration Fields**:
- `type`: Platform/service manager type (e.g., `"darwin"`). Must match a supported backend.
- `data`: Platform-specific configuration object. Structure depends on `type`.

**Platform-Specific Data (darwin/macOS)**:
- `label`: Launchd service identifier in reverse DNS format. Required.
- `keep_alive`: Whether launchd should auto-restart the service if it exits. Required.
- `run_at_load`: Whether the service should start automatically when installed. Required.
- `restrict_dir`: Optional directory to restrict daemon monitoring to; stored as an environment variable for the daemon at launch.

## Normative Schema
- Canonical output schema: `docs/specifications/service_output.schema.json`.
- Implementations MUST validate outputs against this schema; unknown fields are rejected.

## CLI
- Entry: `wksc service`
- Output formats: `--display yaml` (default) or `--display json`

### status
- Command: `wksc service status`
- Behavior: Show installation/running status from the platform service manager, plus stored warnings/errors/log path.
- Output schema: `ServiceStatusOutput`.

### start
- Command: `wksc service start`
- Behavior: Start (or restart) the installed daemon via the platform service manager. Fails if not installed.
- Output schema: `ServiceStartOutput`.

### stop
- Command: `wksc service stop`
- Behavior: Stop the installed daemon via the platform service manager.
- Output schema: `ServiceStopOutput`.

### install
- Command: `wksc service install [--restrict <dir>]`
- Behavior: Install the daemon as a system service. Stores restrict dir (if provided) so the daemon uses it when launched.
- Output schema: `ServiceInstallOutput`.

### uninstall
- Command: `wksc service uninstall`
- Behavior: Remove the system service.
- Output schema: `ServiceUninstallOutput`.

## MCP
- Commands mirror CLI:
  - `wksm_service_status`
  - `wksm_service_start`
  - `wksm_service_stop`
  - `wksm_service_install`
  - `wksm_service_uninstall`
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Unknown/invalid state or schema violation returns schema-conformant error; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- SERVICE.1 — All service config fields required; no defaults in code.
- SERVICE.2 — Commands must emit schema-validated outputs (status/start/stop/install/uninstall).
- SERVICE.3 — CLI/MCP parity: same data and structure for equivalent commands.
- SERVICE.4 — Errors are schema-conformant; no partial success.
- SERVICE.5 — `wksc service start` MUST start the installed daemon via the platform service manager; if not installed, it MUST fail.
- SERVICE.6 — `wksc service install` MUST persist restrict dir (if provided) so the daemon launches with that scope.
- SERVICE.7 — Log path is standardized to `{WKS_HOME}/logs/service.log`; status commands must include this path and surface extracted warnings/errors from the log.

