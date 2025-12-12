# Monitor Specification

## Purpose
Filesystem monitoring: check/sync/status, manage filters and priorities, with consistent CLI/MCP contracts.

## Configuration File Structure
- Location: `{WKS_HOME}/config.json` (override via `WKS_HOME`)
- Composition: Uses `monitor` block as defined in `docs/specifications/wks.md`; all fields required, no defaults in code.

## Normative Schema
- Canonical output schema: `docs/specifications/monitor_output.schema.json`.
- Implementations MUST validate outputs against this schema; unknown fields are rejected.

## CLI

- Entry: `wksc monitor`
- Output formats: `--display yaml` (default) or `--display json`

### status
- Command: `wksc monitor status`
- Behavior: Reports monitoring status, issues, priority directories, counts.
- Output schema: `MonitorStatusOutput` (see normative schema).

### check
- Command: `wksc monitor check <path>`
- Behavior: Determine if a path would be monitored; include priority and decision trace.
- Output schema: `MonitorCheckOutput`.

### sync
- Command: `wksc monitor sync <path> [--recursive]`
- Behavior: Sync file/dir into monitor DB; report counts. If the path does not exist on disk but exists in the monitor database, the record MUST be deleted (removal is treated as a successful sync of zero files with a warning noting the removal).
- Output schema: `MonitorSyncOutput`.

### filter show
- Command: `wksc monitor filter show [<list_name>]`
- Behavior: Show available lists or contents of a list.
- Output schema: `MonitorFilterShowOutput`.

### filter add
- Command: `wksc monitor filter add <list_name> <value>`
- Behavior: Add a value to a filter list.
- Output schema: `MonitorFilterAddOutput`.

### filter remove
- Command: `wksc monitor filter remove <list_name> <value>`
- Behavior: Remove a value from a filter list.
- Output schema: `MonitorFilterRemoveOutput`.

### priority show
- Command: `wksc monitor priority show`
- Behavior: Show priority directories and validation.
- Output schema: `MonitorPriorityShowOutput`.

### priority add
- Command: `wksc monitor priority add <path> <priority>`
- Behavior: Add/update priority for a directory.
- Output schema: `MonitorPriorityAddOutput`.

### priority remove
- Command: `wksc monitor priority remove <path>`
- Behavior: Remove a priority directory.
- Output schema: `MonitorPriorityRemoveOutput`.

## MCP
- Commands mirror CLI:
  - `wksm_monitor_status`
  - `wksm_monitor_check <path>`
  - `wksm_monitor_sync <path> [recursive]`
  - `wksm_monitor_filter_show [list_name]`
  - `wksm_monitor_filter_add <list_name> <value>`
  - `wksm_monitor_filter_remove <list_name> <value>`
  - `wksm_monitor_priority_show`
  - `wksm_monitor_priority_add <path> <priority>`
  - `wksm_monitor_priority_remove <path>`
- Output format: JSON.
- CLI and MCP MUST return the same data and structure for equivalent calls.

## Error Semantics
- Unknown/invalid path/list/priority entry or schema violation returns a schema-conformant error; no partial success.
- All outputs MUST validate against their schemas before returning to CLI or MCP.

## Formal Requirements
- MON.1 — All monitor config fields are required; no defaults in code.
- MON.2 — `wksc monitor status` reports status/validation using `MonitorStatusOutput`.
- MON.3 — `wksc monitor check <path>` requires path and returns `MonitorCheckOutput`.
- MON.4 — `wksc monitor sync <path>` requires path; `--recursive` optional; returns `MonitorSyncOutput`.
- MON.5 — Filter commands must use their respective outputs: show/add/remove.
- MON.6 — Priority commands must use their respective outputs: show/add/remove.
- MON.7 — Schema validation required; unknown/invalid inputs yield schema-conformant errors, no partial success.
